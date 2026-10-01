import os
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("SECRET_KEY", "isolated-google-tests-secret-key-only")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.database import Base, get_db
from app.models.user import User
from app.routers import auth
from app.services import google_auth

CLIENT_ID = "settlo-test.apps.googleusercontent.com"


def google_claims(sub="google-sub-1", name="Ada Lovelace"):
    return {"sub": sub, "email": "ada@example.com", "email_verified": True, "name": name}


class GoogleLoginTest(unittest.TestCase):
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

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def google_login(self, claims):
        with patch.object(auth, "verify_google_token", return_value=claims):
            return self.client.post("/api/auth/google", json={"credential": "token"})

    def test_new_google_account_is_named_from_google(self):
        response = self.google_login(google_claims())

        body = response.json()
        self.assertEqual(
            (body["user"]["username"], body["user"]["google_linked"], self.db.query(User).count()),
            ("Ada Lovelace", True, 1),
        )

    def test_new_google_account_without_a_name_is_named_from_email(self):
        response = self.google_login(google_claims(name=None))

        self.assertEqual(response.json()["user"]["username"], "ada")

    def test_google_login_sets_refresh_cookie(self):
        self.google_login(google_claims())

        self.assertIsNotNone(self.client.cookies.get(auth.REFRESH_COOKIE_NAME))

    def test_google_login_rejects_untrusted_origin(self):
        self.client.headers["Origin"] = "https://attacker.example"

        self.assertEqual(self.google_login(google_claims()).status_code, 403)






class VerifyGoogleTokenTest(unittest.TestCase):
    def setUp(self):
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        signing_key = SimpleNamespace(key=self.private_key.public_key())
        patches = [
            patch.object(settings, "GOOGLE_CLIENT_ID", CLIENT_ID),
            patch.object(
                google_auth._google_keys, "get_signing_key_from_jwt",
                return_value=signing_key,
            ),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def token(self, **overrides):
        now = int(time.time())
        claims = {
            "iss": "https://accounts.google.com", "aud": CLIENT_ID, "sub": "google-sub-1",
            "iat": now, "exp": now + 300, **overrides,
        }
        return jwt.encode(claims, self.private_key, algorithm="RS256")

    def test_accepts_token_issued_for_this_app(self):
        self.assertEqual(google_auth.verify_google_token(self.token())["sub"], "google-sub-1")

    def test_rejects_token_for_another_audience(self):
        with self.assertRaises(google_auth.GoogleAuthError):
            google_auth.verify_google_token(self.token(aud="someone-else"))

    def test_rejects_token_from_another_issuer(self):
        with self.assertRaises(google_auth.GoogleAuthError):
            google_auth.verify_google_token(self.token(iss="https://evil.example"))

    def test_rejects_expired_token(self):
        with self.assertRaises(google_auth.GoogleAuthError):
            google_auth.verify_google_token(self.token(exp=int(time.time()) - 60))


if __name__ == "__main__":
    unittest.main()
