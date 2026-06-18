import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-group-invitations")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import *  # noqa: F401,F403
from app.models.group import Group
from app.models.group_invitation import GroupInvitation, GroupInvitationStatus
from app.models.user import User


class GroupInvitationModelTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _seed(self):
        a = User(phone_number="+15550000001", username="A")
        b = User(phone_number="+15550000002", username="B")
        self.db.add_all([a, b])
        self.db.flush()
        g = Group(name="Trip", created_by=a.id, invite_token="ABCDEF")
        self.db.add(g)
        self.db.flush()
        return a, b, g

    def test_defaults(self):
        a, b, g = self._seed()
        inv = GroupInvitation(group_id=g.id, invited_user_id=b.id, invited_by=a.id)
        self.db.add(inv)
        self.db.commit()
        row = self.db.query(GroupInvitation).one()
        self.assertEqual(row.status, GroupInvitationStatus.PENDING)
        self.assertIsNotNone(row.created_at)
        self.assertIsNone(row.responded_at)

    def test_unique_pair(self):
        a, b, g = self._seed()
        self.db.add(GroupInvitation(group_id=g.id, invited_user_id=b.id, invited_by=a.id))
        self.db.commit()
        self.db.add(GroupInvitation(group_id=g.id, invited_user_id=b.id, invited_by=a.id))
        with self.assertRaises(IntegrityError):
            self.db.commit()
