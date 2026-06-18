import os
import sys
import unittest
from decimal import Decimal
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-friendships-12345")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.database import get_db
from app.main import app

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


class FriendRequestApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(
            bind=self.engine, autocommit=False, autoflush=False
        )
        self.db = self.Session()
        self.a = User(phone_number="+15550000001", username="A")
        self.b = User(phone_number="+15550000002", username="B")
        self.db.add_all([self.a, self.b])
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

    def test_send_request_creates_pending(self):
        res = self.client.post(
            "/api/friends/requests",
            json={"phone_number": self.b.phone_number},
            headers=self._auth(self.a),
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(
            self.db.query(Friendship).count(), 1
        )

    def test_cannot_friend_self(self):
        res = self.client.post(
            "/api/friends/requests",
            json={"phone_number": self.a.phone_number},
            headers=self._auth(self.a),
        )
        self.assertEqual(res.status_code, 400)

    def test_duplicate_request_rejected(self):
        self.client.post(
            "/api/friends/requests",
            json={"phone_number": self.b.phone_number},
            headers=self._auth(self.a),
        )
        res = self.client.post(
            "/api/friends/requests",
            json={"phone_number": self.b.phone_number},
            headers=self._auth(self.a),
        )
        self.assertEqual(res.status_code, 400)

    def test_unknown_phone_404(self):
        res = self.client.post(
            "/api/friends/requests",
            json={"phone_number": "+15559999999"},
            headers=self._auth(self.a),
        )
        self.assertEqual(res.status_code, 404)

    def test_incoming_requests_and_accept(self):
        self.client.post(
            "/api/friends/requests",
            json={"phone_number": self.b.phone_number},
            headers=self._auth(self.a),
        )
        incoming = self.client.get(
            "/api/friends/requests", headers=self._auth(self.b)
        ).json()
        self.assertEqual(len(incoming), 1)
        fid = incoming[0]["id"]
        res = self.client.post(
            f"/api/friends/requests/{fid}/accept", headers=self._auth(self.b)
        )
        self.assertEqual(res.status_code, 204)
        f = self.db.query(Friendship).one()
        self.db.refresh(f)
        self.assertEqual(f.status, FriendshipStatus.ACCEPTED)

    def test_non_addressee_cannot_accept_or_decline(self):
        res = self.client.post(
            "/api/friends/requests",
            json={"phone_number": self.b.phone_number},
            headers=self._auth(self.a),
        )
        self.assertEqual(res.status_code, 201)
        fid = res.json()["id"]
        accept_res = self.client.post(
            f"/api/friends/requests/{fid}/accept", headers=self._auth(self.a)
        )
        self.assertEqual(accept_res.status_code, 404)
        decline_res = self.client.post(
            f"/api/friends/requests/{fid}/decline", headers=self._auth(self.a)
        )
        self.assertEqual(decline_res.status_code, 404)

    def test_decline_deletes_request(self):
        res = self.client.post(
            "/api/friends/requests",
            json={"phone_number": self.b.phone_number},
            headers=self._auth(self.a),
        )
        fid = res.json()["id"]
        res = self.client.post(
            f"/api/friends/requests/{fid}/decline", headers=self._auth(self.b)
        )
        self.assertEqual(res.status_code, 204)
        self.assertEqual(self.db.query(Friendship).count(), 0)


class FriendListApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(
            bind=self.engine, autocommit=False, autoflush=False
        )
        self.db = self.Session()
        self.a = User(phone_number="+15550000001", username="A")
        self.b = User(phone_number="+15550000002", username="B")
        self.db.add_all([self.a, self.b])
        self.db.flush()
        self.db.add(
            Friendship(
                requester_id=self.a.id,
                addressee_id=self.b.id,
                status=FriendshipStatus.ACCEPTED,
            )
        )
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

    def test_list_friends(self):
        res = self.client.get("/api/friends", headers=self._auth(self.a))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], self.b.id)
        self.assertEqual(data[0]["net_balance"], 0.0)

    def test_remove_friend_when_settled(self):
        res = self.client.delete(
            f"/api/friends/{self.b.id}", headers=self._auth(self.a)
        )
        self.assertEqual(res.status_code, 204)
        self.assertEqual(self.db.query(Friendship).count(), 0)


if __name__ == "__main__":
    unittest.main()
