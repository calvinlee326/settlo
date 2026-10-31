import os
import sys
import unittest
from decimal import Decimal
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-group-join-12345")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.database import Base, get_db
from app.main import app
from app.models import *  # noqa: F401,F403
from app.models.friendship import Friendship, FriendshipStatus
from app.models.group import Group, Membership
from app.models.user import User, utcnow


class GroupJoinTest(unittest.TestCase):
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
        self.joiner = User(phone_number="+15550000002", username="Joiner")
        self.db.add_all([self.owner, self.joiner])
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

    def test_join_via_code_adds_member(self):
        res = self.client.post(
            "/api/groups/join/ABCDEF", headers=self._auth(self.joiner)
        )
        self.assertEqual(res.status_code, 200)
        with self.Session() as s:
            count = s.query(Membership).filter(
                Membership.group_id == self.group.id
            ).count()
        self.assertEqual(count, 2)

    def test_join_settled_group_blocked(self):
        with self.Session() as s:
            g = s.query(Group).filter(Group.id == self.group.id).one()
            g.settled_at = utcnow()
            s.commit()
        res = self.client.post(
            "/api/groups/join/ABCDEF", headers=self._auth(self.joiner)
        )
        self.assertEqual(res.status_code, 400)

    def test_rejoin_is_idempotent(self):
        res = self.client.post(
            "/api/groups/join/ABCDEF", headers=self._auth(self.owner)
        )
        self.assertEqual(res.status_code, 200)
        with self.Session() as s:
            count = s.query(Membership).filter(
                Membership.group_id == self.group.id
            ).count()
        self.assertEqual(count, 1)

    def test_join_full_group_blocked(self):
        with self.Session() as s:
            g = s.query(Group).filter(Group.id == self.group.id).one()
            g.max_members = 1
            s.commit()
        res = self.client.post(
            "/api/groups/join/ABCDEF", headers=self._auth(self.joiner)
        )
        self.assertEqual(res.status_code, 400)


class AddFriendMemberTest(GroupJoinTest):
    def _befriend(self, a, b):
        self.db.add(
            Friendship(
                requester_id=a.id, addressee_id=b.id, status=FriendshipStatus.ACCEPTED
            )
        )
        self.db.commit()

    def test_add_friend_to_group(self):
        self._befriend(self.owner, self.joiner)
        res = self.client.post(
            f"/api/groups/{self.group.id}/members",
            json={"user_id": self.joiner.id},
            headers=self._auth(self.owner),
        )
        self.assertEqual(res.status_code, 200)
        with self.Session() as s:
            count = s.query(Membership).filter(
                Membership.group_id == self.group.id
            ).count()
        self.assertEqual(count, 2)

    def test_add_non_friend_rejected(self):
        res = self.client.post(
            f"/api/groups/{self.group.id}/members",
            json={"user_id": self.joiner.id},
            headers=self._auth(self.owner),
        )
        self.assertEqual(res.status_code, 403)


class ShortCodeTest(GroupJoinTest):
    def test_create_group_gets_unguessable_code(self):
        res = self.client.post(
            "/api/groups/",
            json={"name": "Beach"},
            headers=self._auth(self.owner),
        )
        self.assertEqual(res.status_code, 201)
        # 10 characters from the unambiguous alphabet: too many to guess.
        with self.Session() as s:
            g = s.query(Group).filter(Group.name == "Beach").one()
        self.assertEqual(len(g.invite_token), 10)
        self.assertTrue(all(c in "ABCDEFGHJKMNPQRSTUVWXYZ23456789" for c in g.invite_token))


class InviteLinkSecurityTest(GroupJoinTest):
    def _lookup_statuses(self, user, attempts=25):
        return [
            self.client.get("/api/groups/join/WRONG1", headers=self._auth(user)).status_code
            for _ in range(attempts)
        ]

    def test_guessing_invite_codes_is_throttled(self):
        self.assertIn(429, self._lookup_statuses(self.joiner))

    def test_one_users_guessing_does_not_throttle_another(self):
        self._lookup_statuses(self.joiner)

        res = self.client.post("/api/groups/join/ABCDEF", headers=self._auth(self.owner))

        self.assertEqual(res.status_code, 200)

    def _reset(self, user):
        return self.client.post(
            f"/api/groups/{self.group.id}/invite/reset", headers=self._auth(user)
        )

    def test_reset_retires_the_old_invite_link(self):
        self._reset(self.owner)

        res = self.client.post("/api/groups/join/ABCDEF", headers=self._auth(self.joiner))

        self.assertEqual(res.status_code, 404)

    def test_reset_link_lets_people_join(self):
        token = self._reset(self.owner).json()["invite_token"]

        res = self.client.post(f"/api/groups/join/{token}", headers=self._auth(self.joiner))

        self.assertEqual(res.status_code, 200)

    def test_only_the_creator_can_reset_the_invite_link(self):
        self.client.post("/api/groups/join/ABCDEF", headers=self._auth(self.joiner))

        self.assertEqual(self._reset(self.joiner).status_code, 403)
