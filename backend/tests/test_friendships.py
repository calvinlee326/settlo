import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-friendships-12345")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import *  # noqa: F401,F403
from app.models.friendship import Friendship, FriendshipStatus
from app.models.user import User


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


if __name__ == "__main__":
    unittest.main()
