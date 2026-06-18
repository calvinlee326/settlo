import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-group-invitations")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.database import Base, get_db
from app.main import app
from app.models import *  # noqa: F401,F403
from app.models.group import Group, Membership
from app.models.group_invitation import GroupInvitation, GroupInvitationStatus
from app.models.user import User
from fastapi.testclient import TestClient


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


class GroupInvitationApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self.db = self.Session()
        self.owner = User(phone_number="+15550000001", username="Owner")
        self.invitee = User(phone_number="+15550000002", username="Invitee")
        self.db.add_all([self.owner, self.invitee])
        self.db.flush()
        self.group = Group(name="Trip", created_by=self.owner.id, invite_token="ABCDEF")
        self.db.add(self.group)
        self.db.flush()
        self.db.add(Membership(user_id=self.owner.id, group_id=self.group.id))
        self.db.commit()

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def _auth(self, user):
        return {"Authorization": f"Bearer {create_access_token(user.id)}"}

    def test_invite_by_phone_and_accept(self):
        res = self.client.post(
            "/api/group-invitations",
            json={"group_id": self.group.id, "phone_number": self.invitee.phone_number},
            headers=self._auth(self.owner),
        )
        self.assertEqual(res.status_code, 201)

        pending = self.client.get(
            "/api/group-invitations", headers=self._auth(self.invitee)
        ).json()
        self.assertEqual(len(pending), 1)
        inv_id = pending[0]["id"]

        res = self.client.post(
            f"/api/group-invitations/{inv_id}/accept",
            headers=self._auth(self.invitee),
        )
        self.assertEqual(res.status_code, 200)
        with self.Session() as s:
            count = s.query(Membership).filter(
                Membership.group_id == self.group.id
            ).count()
        self.assertEqual(count, 2)

    def test_invite_unknown_phone_404(self):
        res = self.client.post(
            "/api/group-invitations",
            json={"group_id": self.group.id, "phone_number": "+15559999999"},
            headers=self._auth(self.owner),
        )
        self.assertEqual(res.status_code, 404)

    def test_non_member_cannot_invite(self):
        res = self.client.post(
            "/api/group-invitations",
            json={"group_id": self.group.id, "phone_number": self.invitee.phone_number},
            headers=self._auth(self.invitee),
        )
        self.assertEqual(res.status_code, 403)

    def test_decline_deletes(self):
        self.client.post(
            "/api/group-invitations",
            json={"group_id": self.group.id, "phone_number": self.invitee.phone_number},
            headers=self._auth(self.owner),
        )
        with self.Session() as s:
            inv_id = s.query(GroupInvitation).one().id
        res = self.client.post(
            f"/api/group-invitations/{inv_id}/decline",
            headers=self._auth(self.invitee),
        )
        self.assertEqual(res.status_code, 204)
        with self.Session() as s:
            self.assertEqual(s.query(GroupInvitation).count(), 0)

    def test_invite_self_rejected(self):
        res = self.client.post(
            "/api/group-invitations",
            json={"group_id": self.group.id, "phone_number": self.owner.phone_number},
            headers=self._auth(self.owner),
        )
        self.assertEqual(res.status_code, 400)

    def test_invite_to_settled_group_blocked(self):
        from app.models.user import utcnow
        with self.Session() as s:
            g = s.query(Group).filter(Group.id == self.group.id).one()
            g.settled_at = utcnow()
            s.commit()
        res = self.client.post(
            "/api/group-invitations",
            json={"group_id": self.group.id, "phone_number": self.invitee.phone_number},
            headers=self._auth(self.owner),
        )
        self.assertEqual(res.status_code, 400)
