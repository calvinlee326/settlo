import os
import sys
import unittest
from decimal import Decimal
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-friendships-12345")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
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
        a = User(phone_number="+15550000001", username="A", handle="alice")
        b = User(phone_number="+15550000002", username="B", handle="bob")
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
        self.a = User(phone_number="+15550000001", username="A", handle="alice")
        self.b = User(phone_number="+15550000002", username="B", handle="bob")
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
        self.a = User(phone_number="+15550000001", username="A", handle="alice")
        self.b = User(phone_number="+15550000002", username="B", handle="bob")
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

    def test_adding_by_id_makes_friends_without_approval(self):
        res = self.client.post(
            "/api/friends/requests",
            json={"handle": self.b.handle},
            headers=self._auth(self.a),
        )
        b_friends = self.client.get("/api/friends", headers=self._auth(self.b)).json()
        self.assertEqual(
            (res.status_code, [f["id"] for f in b_friends]), (201, [self.a.id])
        )

    def test_cannot_friend_self(self):
        res = self.client.post(
            "/api/friends/requests",
            json={"handle": self.a.handle},
            headers=self._auth(self.a),
        )
        self.assertEqual(res.status_code, 400)

    def test_adding_an_existing_friend_is_rejected(self):
        self.client.post(
            "/api/friends/requests",
            json={"handle": self.b.handle},
            headers=self._auth(self.a),
        )
        res = self.client.post(
            "/api/friends/requests",
            json={"handle": self.a.handle},
            headers=self._auth(self.b),
        )
        self.assertEqual(res.status_code, 400)

    def test_unknown_phone_404(self):
        res = self.client.post(
            "/api/friends/requests",
            json={"handle": "nobody"},
            headers=self._auth(self.a),
        )
        self.assertEqual(res.status_code, 404)


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
        self.a = User(phone_number="+15550000001", username="A", handle="alice")
        self.b = User(phone_number="+15550000002", username="B", handle="bob")
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

    def test_friend_list_query_count_does_not_grow_with_friends(self):
        def count_queries():
            statements = []
            listener = lambda conn, cur, stmt, params, ctx, many: statements.append(stmt)
            event.listen(self.engine, "before_cursor_execute", listener)
            try:
                res = self.client.get("/api/friends", headers=self._auth(self.a))
            finally:
                event.remove(self.engine, "before_cursor_execute", listener)
            return len(res.json()), len(statements)

        few_friends, few_queries = count_queries()
        for i in range(5):
            friend = User(phone_number=f"+1555000010{i}", username=f"F{i}", handle=f"friend{i}")
            self.db.add(friend)
            self.db.flush()
            self.db.add(Friendship(
                requester_id=self.a.id, addressee_id=friend.id, status=FriendshipStatus.ACCEPTED
            ))
        self.db.commit()
        many_friends, many_queries = count_queries()

        self.assertEqual((few_friends, many_friends), (1, 6))
        self.assertEqual(few_queries, many_queries)

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
        with self.Session() as s:
            self.assertEqual(s.query(Friendship).count(), 0)

    def test_remove_non_friend_returns_404(self):
        res = self.client.delete(
            "/api/friends/nonexistent", headers=self._auth(self.a)
        )
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
