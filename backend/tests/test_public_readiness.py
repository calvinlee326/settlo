import os
import sys
import unittest
import importlib
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-public-readiness")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.schema import MetaData

from app.core.config import Settings
from app.database import Base, database_url_for_sqlalchemy
from app.models import *  # noqa: F401,F403
from app.models.expense import Expense, ExpenseSplit, Settlement, SplitType
from app.models.group import Group, Membership
from app.models.user import User
from app.routers.groups import _group_detail, list_my_groups, remove_member
from app.routers.settlements import get_settlements, mark_paid


class PublicReadinessTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def create_group_with_members(self):
        creator = User(phone_number="+15550000001", username="Creator")
        member = User(phone_number="+15550000002", username="Member")
        self.db.add_all([creator, member])
        self.db.flush()

        group = Group(name="Trip", created_by=creator.id)
        self.db.add(group)
        self.db.flush()
        self.db.add_all(
            [
                Membership(user_id=creator.id, group_id=group.id),
                Membership(user_id=member.id, group_id=group.id),
            ]
        )
        self.db.commit()
        return creator, member, group

    def create_expense(self, group, payer, creator, splits):
        expense = Expense(
            group_id=group.id,
            paid_by=payer.id,
            title="Dinner",
            amount=Decimal("100.00"),
            currency="USD",
            split_type=SplitType.CUSTOM,
            created_by=creator.id,
        )
        self.db.add(expense)
        self.db.flush()
        for user, amount in splits:
            self.db.add(
                ExpenseSplit(
                    expense_id=expense.id,
                    user_id=user.id,
                    amount=Decimal(amount),
                )
            )
        self.db.commit()
        return expense

    def test_member_detail_does_not_expose_phone_numbers(self):
        creator, member, group = self.create_group_with_members()

        detail = _group_detail(self.db, group)

        member_payloads = [m.model_dump() for m in detail.members]
        self.assertNotIn("phone_number", member_payloads[0])
        self.assertEqual(
            {m["id"] for m in member_payloads}, {creator.id, member.id}
        )

    def test_member_with_financial_activity_cannot_be_removed(self):
        creator, member, group = self.create_group_with_members()
        self.create_expense(
            group,
            payer=creator,
            creator=creator,
            splits=[(creator, "50.00"), (member, "50.00")],
        )

        with self.assertRaises(HTTPException) as exc:
            remove_member(group.id, member.id, current_user=creator, db=self.db)

        self.assertEqual(exc.exception.status_code, 400)
        membership = (
            self.db.query(Membership)
            .filter(Membership.group_id == group.id, Membership.user_id == member.id)
            .first()
        )
        self.assertIsNotNone(membership)

    def test_get_settlements_does_not_persist_unpaid_settlements(self):
        creator, member, group = self.create_group_with_members()
        self.create_expense(
            group,
            payer=creator,
            creator=creator,
            splits=[(creator, "50.00"), (member, "50.00")],
        )

        result = get_settlements(group.id, current_user=creator, db=self.db)

        self.assertEqual(self.db.query(Settlement).count(), 0)
        self.assertEqual(len(result.settlements), 1)
        self.assertEqual(result.settlements[0].from_user, member.id)
        self.assertEqual(result.settlements[0].to_user, creator.id)
        self.assertEqual(result.settlements[0].amount, 50.0)

    def test_mark_paid_persists_computed_settlement(self):
        creator, member, group = self.create_group_with_members()
        self.create_expense(
            group,
            payer=creator,
            creator=creator,
            splits=[(creator, "50.00"), (member, "50.00")],
        )
        draft = get_settlements(group.id, current_user=creator, db=self.db).settlements[0]

        paid = mark_paid(group.id, draft.id, current_user=member, db=self.db)

        self.assertTrue(paid.is_paid)
        self.assertEqual(paid.from_user, member.id)
        self.assertEqual(paid.to_user, creator.id)
        self.assertEqual(self.db.query(Settlement).count(), 1)

    def test_secret_key_must_be_configured(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValidationError):
                Settings(_env_file=None)

    def test_backend_has_postgres_dependency(self):
        requirements = Path(__file__).resolve().parents[1] / "requirements.txt"

        self.assertIn("psycopg[binary]", requirements.read_text())

    def test_plain_postgres_database_url_uses_psycopg_driver(self):
        self.assertEqual(
            database_url_for_sqlalchemy("postgresql://user:pass@host:5432/db"),
            "postgresql+psycopg://user:pass@host:5432/db",
        )
        self.assertEqual(
            database_url_for_sqlalchemy("postgres://user:pass@host:5432/db"),
            "postgresql+psycopg://user:pass@host:5432/db",
        )

    def test_alembic_uses_same_database_url_driver(self):
        alembic_env = Path(__file__).resolve().parents[1] / "alembic" / "env.py"
        text = alembic_env.read_text()

        self.assertIn("database_url_for_sqlalchemy(settings.DATABASE_URL)", text)

    def test_app_import_does_not_create_tables(self):
        existing = sys.modules.pop("app.main", None)
        try:
            with patch.object(
                MetaData, "create_all", side_effect=AssertionError("create_all called")
            ):
                importlib.import_module("app.main")
        finally:
            sys.modules.pop("app.main", None)
            if existing is not None:
                sys.modules["app.main"] = existing

    def test_listing_groups_does_not_scale_queries_with_group_count(self):
        """Guards the member-count batching: a per-group COUNT would grow this."""
        users = [User(phone_number=f"+1555444{i:04d}", username=f"U{i}") for i in range(4)]
        self.db.add_all(users)
        self.db.flush()

        def make_groups(count, offset):
            for gi in range(count):
                group = Group(
                    name=f"G{offset + gi}",
                    created_by=users[0].id,
                    invite_token=f"scale-{offset + gi}",
                )
                self.db.add(group)
                self.db.flush()
                for user in users:
                    self.db.add(Membership(group_id=group.id, user_id=user.id))
            self.db.commit()

        def count_queries():
            statements = []
            listener = lambda conn, cur, stmt, params, ctx, many: statements.append(stmt)
            event.listen(self.engine, "before_cursor_execute", listener)
            try:
                groups = list_my_groups(current_user=users[0], db=self.db)
            finally:
                event.remove(self.engine, "before_cursor_execute", listener)
            return len(groups), len(statements)

        make_groups(3, 0)
        few_groups, few_queries = count_queries()
        make_groups(15, 3)
        many_groups, many_queries = count_queries()

        self.assertEqual((few_groups, many_groups), (3, 18))
        self.assertEqual(few_queries, many_queries)








if __name__ == "__main__":
    unittest.main()
