import asyncio
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-live-updates-123456")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.database import Base, get_db
from app.main import app
from app.models import *  # noqa: F401,F403
from app.models.user import User
from app.services import changes


class WaitForChangeTest(unittest.TestCase):
    def test_returns_at_once_when_client_is_behind(self):
        seen = asyncio.run(changes.wait_for_change(None))
        started = time.monotonic()
        asyncio.run(changes.wait_for_change(seen - 1))
        self.assertLess(time.monotonic() - started, 0.1)

    def test_wakes_when_a_write_lands_during_the_wait(self):
        async def scenario():
            seen = await changes.wait_for_change(None)
            waiting = asyncio.create_task(changes.wait_for_change(seen))
            await asyncio.sleep(0.05)
            changes.bump()
            started = time.monotonic()
            version = await waiting
            return version - seen, time.monotonic() - started

        with patch.object(changes, "WAIT_SECONDS", 5):
            moved, waited = asyncio.run(scenario())
        self.assertEqual((moved, waited < 1), (1, True))


class ChangesApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        with self.Session() as db:
            user = User(username="A", handle="alice")
            db.add(user)
            db.commit()
            self.headers = {"Authorization": f"Bearer {create_access_token(user.id)}"}

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.wait = patch.object(changes, "WAIT_SECONDS", 0.1)
        self.wait.start()

    def tearDown(self):
        self.wait.stop()
        app.dependency_overrides.clear()
        self.engine.dispose()

    def version(self, seen=None):
        params = {} if seen is None else {"seen": seen}
        res = self.client.get("/api/changes", params=params, headers=self.headers)
        return res.json()["version"]

    def test_a_write_moves_the_version(self):
        before = self.version()
        self.client.post("/api/groups/", json={"name": "Trip"}, headers=self.headers)
        self.assertEqual(self.version(), before + 1)

    def test_a_rejected_write_leaves_the_version(self):
        before = self.version()
        self.client.post("/api/groups/", json={}, headers=self.headers)
        self.assertEqual(self.version(), before)

    def test_waiting_with_nothing_new_returns_the_same_version(self):
        before = self.version()
        self.assertEqual(self.version(seen=before), before)

    def test_requires_sign_in(self):
        self.assertEqual(self.client.get("/api/changes").status_code, 401)


if __name__ == "__main__":
    unittest.main()
