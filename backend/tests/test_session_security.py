import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("SECRET_KEY", "isolated-session-tests-secret-key-only")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.database import Base, get_db
from app.models.user import TokenBlacklist
from app.routers import auth


class SessionSecurityTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        app = FastAPI()
        app.include_router(auth.router)

        def isolated_db():
            yield self.db

        app.dependency_overrides[get_db] = isolated_db
        self.client = TestClient(app, base_url="https://testserver")
        self.client.headers["Origin"] = settings.FRONTEND_URL
        self.dev_otp = patch.object(settings, "DEV_OTP_CODE", "000000")
        self.dev_otp.start()

    def tearDown(self):
        self.dev_otp.stop()
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def login(self):
        response = self.client.post("/api/auth/verify-otp", json={
            "phone_number": "5550000001", "code": "000000",
        })
        self.assertEqual(response.status_code, 200)
        return response

    def test_cookie_login_refresh_and_logout_revocation(self):
        response = self.login()
        cookie_header = response.headers["set-cookie"]
        self.assertTrue(all(value in cookie_header for value in (
            "HttpOnly", "Secure", "SameSite=none", "Path=/api/auth", "Max-Age=604800"
        )))
        self.assertNotIn("refresh_token", response.json())
        refresh_token = self.client.cookies.get(auth.REFRESH_COOKIE_NAME)
        refreshed = self.client.post("/api/auth/refresh")
        self.assertEqual(refreshed.status_code, 200)
        access_token = refreshed.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 200)
        logout = self.client.post("/api/auth/logout", headers=headers)
        self.assertEqual(logout.status_code, 200)
        self.assertIn("Max-Age=0", logout.headers["set-cookie"])
        self.assertIsNone(self.client.cookies.get(auth.REFRESH_COOKIE_NAME))
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 401)
        self.client.cookies.set(auth.REFRESH_COOKIE_NAME, refresh_token)
        self.assertEqual(self.client.post("/api/auth/refresh").status_code, 401)
        self.assertEqual(self.db.query(TokenBlacklist).count(), 2)

    def test_cookie_endpoints_reject_missing_and_untrusted_origins(self):
        for origin in (None, "null", "https://attacker.example"):
            with self.subTest(origin=origin):
                self.client.headers.pop("Origin", None)
                if origin:
                    self.client.headers["Origin"] = origin
                for endpoint, body in (
                    ("verify-otp", {"phone_number": "5550000001", "code": "000000"}),
                    ("refresh", None), ("logout", None),
                ):
                    self.assertEqual(self.client.post(f"/api/auth/{endpoint}", json=body).status_code, 403)

    def test_legacy_body_cannot_refresh_and_cookie_only_logout_works(self):
        self.login()
        refresh_token = self.client.cookies.get(auth.REFRESH_COOKIE_NAME)
        self.client.cookies.clear()
        self.assertEqual(self.client.post("/api/auth/refresh", json={
            "refresh_token": refresh_token,
        }).status_code, 401)
        self.client.cookies.set(auth.REFRESH_COOKIE_NAME, refresh_token)
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 200)
        self.client.cookies.set(auth.REFRESH_COOKIE_NAME, refresh_token)
        self.assertEqual(self.client.post("/api/auth/refresh").status_code, 401)


if __name__ == "__main__":
    unittest.main()
