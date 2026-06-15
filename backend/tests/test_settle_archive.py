import os
import sys
import unittest
from decimal import Decimal
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-settle-archive")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import *  # noqa: F401,F403
from app.models.expense import Expense, ExpenseSplit, Settlement
from app.models.group import Group, Membership
from app.models.user import User


class SettleArchiveTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(
            bind=self.engine, autocommit=False, autoflush=False
        )()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _group(self):
        a = User(phone_number="+15550000001", username="A")
        b = User(phone_number="+15550000002", username="B")
        self.db.add_all([a, b])
        self.db.flush()
        g = Group(name="Trip", created_by=a.id)
        self.db.add(g)
        self.db.flush()
        self.db.add_all([
            Membership(user_id=a.id, group_id=g.id),
            Membership(user_id=b.id, group_id=g.id),
        ])
        self.db.commit()
        return a, b, g

    def _expense(self, group, payer, a, b, total, share_a, share_b):
        e = Expense(
            group_id=group.id, paid_by=payer.id, title="X",
            amount=Decimal(total), created_by=payer.id,
        )
        self.db.add(e)
        self.db.flush()
        self.db.add_all([
            ExpenseSplit(expense_id=e.id, user_id=a.id, amount=Decimal(share_a)),
            ExpenseSplit(expense_id=e.id, user_id=b.id, amount=Decimal(share_b)),
        ])
        self.db.commit()
        return e

    def test_group_settle_archive_columns_default_none(self):
        a, b, g = self._group()
        reloaded = self.db.query(Group).filter(Group.id == g.id).one()
        self.assertIsNone(reloaded.settled_at)
        self.assertIsNone(reloaded.settled_by)
        self.assertIsNone(reloaded.deleted_at)

    def test_get_group_or_404_excludes_soft_deleted(self):
        from fastapi import HTTPException
        from app.routers.groups import get_group_or_404
        from app.models.user import utcnow

        a, b, g = self._group()
        g.deleted_at = utcnow()
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            get_group_or_404(self.db, g.id)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_delete_group_is_soft(self):
        from app.routers.groups import delete_group, list_my_groups

        a, b, g = self._group()
        delete_group(g.id, current_user=a, db=self.db)
        row = self.db.query(Group).filter(Group.id == g.id).one()
        self.assertIsNotNone(row.deleted_at)
        listed = list_my_groups(current_user=a, db=self.db)
        self.assertEqual(listed, [])

    def test_list_my_groups_reports_total_and_settled_at(self):
        from app.routers.groups import list_my_groups

        a, b, g = self._group()
        self._expense(g, a, a, b, "10.00", "5.00", "5.00")
        listed = list_my_groups(current_user=a, db=self.db)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0].total, 10.0)
        self.assertIsNone(listed[0].settled_at)

    def test_confirm_archives_group_and_persists_settlement(self):
        from app.routers.settlements import confirm_settlement, get_settlements

        a, b, g = self._group()
        self._expense(g, a, a, b, "10.00", "5.00", "5.00")  # B owes A 5
        confirm_settlement(g.id, current_user=a, db=self.db)

        row = self.db.query(Group).filter(Group.id == g.id).one()
        self.assertIsNotNone(row.settled_at)
        self.assertEqual(row.settled_by, a.id)

        persisted = self.db.query(Settlement).filter(
            Settlement.group_id == g.id, Settlement.is_paid.is_(True)
        ).all()
        self.assertEqual(len(persisted), 1)
        self.assertEqual(persisted[0].from_user, b.id)
        self.assertEqual(persisted[0].to_user, a.id)

        result = get_settlements(g.id, current_user=a, db=self.db)
        self.assertEqual(result.settlements, [])
        self.assertEqual(len(result.paid_settlements), 1)
        self.assertTrue(all(abs(bal.balance) < 0.005 for bal in result.balances))

    def test_confirm_rejects_when_already_settled(self):
        from fastapi import HTTPException
        from app.routers.settlements import confirm_settlement

        a, b, g = self._group()
        self._expense(g, a, a, b, "10.00", "5.00", "5.00")
        confirm_settlement(g.id, current_user=a, db=self.db)
        with self.assertRaises(HTTPException) as ctx:
            confirm_settlement(g.id, current_user=a, db=self.db)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_confirm_rejects_when_no_expenses(self):
        from fastapi import HTTPException
        from app.routers.settlements import confirm_settlement

        a, b, g = self._group()
        with self.assertRaises(HTTPException) as ctx:
            confirm_settlement(g.id, current_user=a, db=self.db)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_confirm_with_zero_debt_still_archives(self):
        from app.routers.settlements import confirm_settlement

        a, b, g = self._group()
        self._expense(g, a, a, b, "10.00", "10.00", "0.00")  # nets to zero
        confirm_settlement(g.id, current_user=a, db=self.db)
        row = self.db.query(Group).filter(Group.id == g.id).one()
        self.assertIsNotNone(row.settled_at)
        self.assertEqual(
            self.db.query(Settlement).filter(Settlement.group_id == g.id).count(), 0
        )


    def test_create_expense_blocked_when_settled(self):
        from fastapi import HTTPException
        from app.routers.expenses import create_expense
        from app.routers.settlements import confirm_settlement
        from app.schemas.expense import ExpenseCreate

        a, b, g = self._group()
        self._expense(g, a, a, b, "10.00", "5.00", "5.00")
        confirm_settlement(g.id, current_user=a, db=self.db)

        body = ExpenseCreate(
            title="Late", amount=Decimal("4.00"), paid_by=a.id, split_type="EQUAL"
        )
        with self.assertRaises(HTTPException) as ctx:
            create_expense(g.id, body, current_user=a, db=self.db)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_delete_expense_blocked_when_settled(self):
        from fastapi import HTTPException
        from app.routers.expenses import delete_expense
        from app.routers.settlements import confirm_settlement

        a, b, g = self._group()
        e = self._expense(g, a, a, b, "10.00", "5.00", "5.00")
        confirm_settlement(g.id, current_user=a, db=self.db)
        with self.assertRaises(HTTPException) as ctx:
            delete_expense(g.id, e.id, current_user=a, db=self.db)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_join_and_preview_reject_soft_deleted_group(self):
        from fastapi import HTTPException
        from app.routers.groups import delete_group, preview_invite, join_group
        from app.models.user import User

        a, b, g = self._group()
        token = g.invite_token
        delete_group(g.id, current_user=a, db=self.db)

        c = User(phone_number="+15550000003", username="C")
        self.db.add(c)
        self.db.commit()

        with self.assertRaises(HTTPException) as p:
            preview_invite(token, current_user=c, db=self.db)
        self.assertEqual(p.exception.status_code, 404)
        with self.assertRaises(HTTPException) as j:
            join_group(token, current_user=c, db=self.db)
        self.assertEqual(j.exception.status_code, 404)

    def test_mark_paid_blocked_when_settled(self):
        from fastapi import HTTPException
        from app.routers.settlements import confirm_settlement, mark_paid

        a, b, g = self._group()
        self._expense(g, a, a, b, "10.00", "5.00", "5.00")
        confirm_settlement(g.id, current_user=a, db=self.db)
        with self.assertRaises(HTTPException) as ctx:
            mark_paid(g.id, "draft_anything", current_user=a, db=self.db)
        self.assertEqual(ctx.exception.status_code, 400)


    def test_join_resplits_equal_expenses(self):
        from app.routers.expenses import create_expense
        from app.routers.groups import join_group
        from app.routers.settlements import _compute_balances
        from app.schemas.expense import ExpenseCreate

        a = User(phone_number="+15550000010", username="A2")
        self.db.add(a)
        self.db.flush()
        g = Group(name="Solo", created_by=a.id)
        self.db.add(g)
        self.db.flush()
        self.db.add(Membership(user_id=a.id, group_id=g.id))
        self.db.commit()

        # A is the only member; a $30 equal expense splits to A alone
        body = ExpenseCreate(
            title="Dinner", amount=Decimal("30.00"), paid_by=a.id, split_type="EQUAL"
        )
        create_expense(g.id, body, current_user=a, db=self.db)

        b = User(phone_number="+15550000011", username="B2")
        self.db.add(b)
        self.db.commit()
        join_group(g.invite_token, current_user=b, db=self.db)

        balances = _compute_balances(self.db, g.id)
        self.assertEqual(balances[a.id].quantize(Decimal("0.01")), Decimal("15.00"))
        self.assertEqual(balances[b.id].quantize(Decimal("0.01")), Decimal("-15.00"))


if __name__ == "__main__":
    unittest.main()
