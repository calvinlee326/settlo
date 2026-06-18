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


class ShortCodeTest(GroupJoinTest):
    def test_create_group_gets_short_code(self):
        res = self.client.post(
            "/api/groups/",
            json={"name": "Beach"},
            headers=self._auth(self.owner),
        )
        self.assertEqual(res.status_code, 201)
        # The created group's code is short and from the unambiguous alphabet.
        with self.Session() as s:
            g = s.query(Group).filter(Group.name == "Beach").one()
        self.assertEqual(len(g.invite_token), 6)
        self.assertTrue(all(c in "ABCDEFGHJKMNPQRSTUVWXYZ23456789" for c in g.invite_token))
