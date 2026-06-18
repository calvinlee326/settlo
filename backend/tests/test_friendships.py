import os
import sys
import unittest
from decimal import Decimal
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-friendships-12345")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import *  # noqa: F401,F403
from app.models.expense import Expense, ExpenseSplit, Settlement
from app.models.friendship import Friendship, FriendshipStatus
from app.models.user import User
from app.services import friends as friends_svc


class FriendshipModelTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _users(self):
        a = User(phone_number="+15550000001", username="A")
        b = User(phone_number="+15550000002", username="B")
        self.db.add_all([a, b])
        self.db.commit()
        return a, b

    def test_friendship_defaults(self):
        a, b = self._users()
        f = Friendship(requester_id=a.id, addressee_id=b.id)
        self.db.add(f)
        self.db.commit()
        reloaded = self.db.query(Friendship).one()
        self.assertEqual(reloaded.status, FriendshipStatus.PENDING)
        self.assertIsNotNone(reloaded.created_at)
        self.assertIsNone(reloaded.responded_at)

    def test_friendship_pair_unique(self):
        a, b = self._users()
        self.db.add(Friendship(requester_id=a.id, addressee_id=b.id))
        self.db.commit()
        self.db.add(Friendship(requester_id=a.id, addressee_id=b.id))
        with self.assertRaises(IntegrityError):
            self.db.commit()


class FriendServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)()
        self.a = User(phone_number="+15550000001", username="A")
        self.b = User(phone_number="+15550000002", username="B")
        self.db.add_all([self.a, self.b])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_get_friendship_either_direction(self):
        f = Friendship(requester_id=self.a.id, addressee_id=self.b.id)
        self.db.add(f)
        self.db.commit()
        self.assertIsNotNone(friends_svc.get_friendship(self.db, self.a.id, self.b.id))
        self.assertIsNotNone(friends_svc.get_friendship(self.db, self.b.id, self.a.id))

    def test_are_friends_requires_accepted(self):
        f = Friendship(requester_id=self.a.id, addressee_id=self.b.id)
        self.db.add(f)
        self.db.commit()
        self.assertFalse(friends_svc.are_friends(self.db, self.a.id, self.b.id))
        f.status = FriendshipStatus.ACCEPTED
        self.db.commit()
        self.assertTrue(friends_svc.are_friends(self.db, self.a.id, self.b.id))

    def test_friend_balance_zero_when_no_expenses(self):
        self.assertEqual(
            friends_svc.friend_balance(self.db, self.a.id, self.b.id), Decimal("0.00")
        )


if __name__ == "__main__":
    unittest.main()
