import os
import sys
import unittest
from decimal import Decimal
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-direct-expenses")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import *  # noqa: F401,F403
from app.models.expense import Expense, ExpenseSplit
from app.models.user import User


class NullableGroupIdTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_expense_allows_null_group(self):
        u = User(phone_number="+15550000001", username="A")
        self.db.add(u)
        self.db.flush()
        e = Expense(
            group_id=None,
            paid_by=u.id,
            title="Coffee",
            amount=Decimal("4.00"),
            created_by=u.id,
        )
        self.db.add(e)
        self.db.commit()
        self.assertIsNone(self.db.query(Expense).one().group_id)
