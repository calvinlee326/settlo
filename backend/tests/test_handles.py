import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-user-handles-123")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import create_access_token
from app.database import Base, get_db
from app.main import app
from app.models import *  # noqa: F401,F403
from app.models.friendship import Friendship
from app.models.group import Group, Membership
from app.models.group_invitation import GroupInvitation
from app.models.user import User


class HandleApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self.db = self.Session()
        self.ada = User(phone_number="+15550000001", username="Ada", handle="ada")
        self.bob = User(phone_number="+15550000002", username="Bob")
        self.db.add_all([self.ada, self.bob])
        self.db.commit()

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app, base_url="https://testserver")

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def _auth(self, user):
        return {"Authorization": f"Bearer {create_access_token(user.id)}"}

    def set_handle(self, user, handle):
        return self.client.post(
            "/api/auth/set-handle", json={"handle": handle}, headers=self._auth(user)
        )

    def test_handle_is_stored_lowercase_without_at_sign(self):
        self.set_handle(self.bob, "@Bob.Builder")

        me = self.client.get("/api/auth/me", headers=self._auth(self.bob)).json()

        self.assertEqual(me["handle"], "bob.builder")

    def test_handle_taken_by_another_user_in_any_case_is_rejected(self):
        self.assertEqual(self.set_handle(self.bob, "ADA").status_code, 409)

    def test_user_can_resave_their_own_handle(self):
        self.assertEqual(self.set_handle(self.ada, "ada").status_code, 200)

    def test_malformed_handles_are_rejected(self):
        for handle in (
            "ab", "has space", ".ada", "ada.", "a..b", "x" * 31, "ada!", "12345", "9095550101",
        ):
            with self.subTest(handle=handle):
                self.assertEqual(self.set_handle(self.bob, handle).status_code, 422)

    def check(self, user, handle):
        return self.client.get(
            "/api/auth/handle-available", params={"handle": handle}, headers=self._auth(user)
        )

    def test_free_handle_is_available(self):
        self.assertTrue(self.check(self.bob, "bob").json()["available"])

    def test_handle_taken_in_any_case_is_unavailable(self):
        self.assertEqual(
            self.check(self.bob, "@ADA").json(),
            {"handle": "ada", "available": False, "message": "That ID is already taken"},
        )

    def test_own_handle_counts_as_available(self):
        self.assertTrue(self.check(self.ada, "ada").json()["available"])

    def test_reserved_handles_are_unavailable(self):
        for handle in ("Admin", "support", "settlo", "settlo.support", "the_settlo_team"):
            with self.subTest(handle=handle):
                self.assertFalse(self.check(self.bob, handle).json()["available"])

    def test_malformed_handle_check_is_rejected(self):
        self.assertEqual(self.check(self.bob, "a..b").status_code, 422)

    def test_setting_a_reserved_handle_is_rejected(self):
        res = self.set_handle(self.bob, "admin")

        self.assertEqual(
            (res.status_code, res.json()["detail"]), (409, "That ID is reserved")
        )

    def test_friend_request_by_handle_reaches_that_user(self):
        res = self.client.post(
            "/api/friends/requests", json={"handle": "@ADA"}, headers=self._auth(self.bob)
        )

        self.assertEqual(
            (res.status_code, self.db.query(Friendship).one().addressee_id),
            (201, self.ada.id),
        )

    def test_friend_request_to_unknown_handle_is_404(self):
        res = self.client.post(
            "/api/friends/requests", json={"handle": "nobody"}, headers=self._auth(self.bob)
        )

        self.assertEqual(res.status_code, 404)

    def test_friend_request_needs_exactly_one_of_handle_or_phone(self):
        for body in ({}, {"handle": "ada", "phone_number": "+15550000001"}):
            with self.subTest(body=body):
                res = self.client.post(
                    "/api/friends/requests", json=body, headers=self._auth(self.bob)
                )
                self.assertEqual(res.status_code, 422)

    def test_group_invite_by_handle_reaches_that_user(self):
        group = Group(name="Trip", created_by=self.bob.id, invite_token="ABCDEF")
        self.db.add(group)
        self.db.flush()
        self.db.add(Membership(user_id=self.bob.id, group_id=group.id))
        self.db.commit()

        res = self.client.post(
            "/api/group-invitations",
            json={"group_id": group.id, "handle": "ada"},
            headers=self._auth(self.bob),
        )

        self.assertEqual(
            (res.status_code, self.db.query(GroupInvitation).one().invited_user_id),
            (201, self.ada.id),
        )

    def test_named_user_without_handle_skips_signup_step(self):
        self.client.headers["Origin"] = settings.FRONTEND_URL
        with patch.object(settings, "DEV_OTP_CODE", "000000"):
            res = self.client.post(
                "/api/auth/verify-otp", json={"phone_number": "5550000002", "code": "000000"}
            )

        self.assertFalse(res.json()["is_new_user"])


if __name__ == "__main__":
    unittest.main()
