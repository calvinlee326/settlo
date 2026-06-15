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


if __name__ == "__main__":
    unittest.main()
