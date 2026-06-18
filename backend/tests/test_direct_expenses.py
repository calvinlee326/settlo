import os
import sys
import unittest
from decimal import Decimal
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-direct-expenses")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.database import Base, get_db
from app.main import app
from app.models import *  # noqa: F401,F403
from app.models.expense import Expense, ExpenseSplit
from app.models.friendship import Friendship, FriendshipStatus
from app.models.user import User


class NullableGroupIdTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_expense_allows_null_group(self):
        u = User(phone_number="+15550000001", username="A")
        self.db.add(u)
        self.db.flush()
        e = Expense(
            group_id=None,
            paid_by=u.id,
            title="Coffee",
            amount=Decimal("4.00"),
            created_by=u.id,
        )
        self.db.add(e)
        self.db.commit()
        self.assertIsNone(self.db.query(Expense).one().group_id)


class DirectExpenseApiTest(unittest.TestCase):
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
        self.c = User(phone_number="+15550000003", username="C")
        self.db.add_all([self.a, self.b, self.c])
        self.db.flush()
        self.db.add_all([
            Friendship(
                requester_id=self.a.id,
                addressee_id=self.b.id,
                status=FriendshipStatus.ACCEPTED,
            ),
            Friendship(
                requester_id=self.a.id,
                addressee_id=self.c.id,
                status=FriendshipStatus.ACCEPTED,
            ),
        ])
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

    def test_create_equal_direct_expense(self):
        res = self.client.post(
            "/api/direct-expenses",
            json={
                "title": "Lunch",
                "amount": "30.00",
                "paid_by": self.a.id,
                "split_type": "EQUAL",
                "participant_ids": [self.a.id, self.b.id, self.c.id],
            },
            headers=self._auth(self.a),
        )
        self.assertEqual(res.status_code, 201)
        body = res.json()
        self.assertIsNone(body["group_id"])
        self.assertEqual(len(body["splits"]), 3)

    def test_reject_non_friend_participant(self):
        stranger = User(phone_number="+15550000009", username="Z")
        self.db.add(stranger)
        self.db.commit()
        res = self.client.post(
            "/api/direct-expenses",
            json={
                "title": "Lunch",
                "amount": "10.00",
                "paid_by": self.a.id,
                "split_type": "EQUAL",
                "participant_ids": [self.a.id, stranger.id],
            },
            headers=self._auth(self.a),
        )
        self.assertEqual(res.status_code, 403)

    def test_friend_expenses_listing(self):
        self.client.post(
            "/api/direct-expenses",
            json={
                "title": "Lunch",
                "amount": "20.00",
                "paid_by": self.a.id,
                "split_type": "EQUAL",
                "participant_ids": [self.a.id, self.b.id],
            },
            headers=self._auth(self.a),
        )
        res = self.client.get(
            f"/api/friends/{self.b.id}/expenses", headers=self._auth(self.a)
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 1)

    def test_paid_by_not_in_participants_rejected(self):
        res = self.client.post(
            "/api/direct-expenses",
            json={
                "title": "Coffee",
                "amount": "10.00",
                "paid_by": self.b.id,
                "split_type": "EQUAL",
                "participant_ids": [self.a.id, self.c.id],
            },
            headers=self._auth(self.a),
        )
        self.assertEqual(res.status_code, 400)

    def test_delete_by_creator(self):
        create_res = self.client.post(
            "/api/direct-expenses",
            json={
                "title": "Dinner",
                "amount": "20.00",
                "paid_by": self.a.id,
                "split_type": "EQUAL",
                "participant_ids": [self.a.id, self.b.id],
            },
            headers=self._auth(self.a),
        )
        self.assertEqual(create_res.status_code, 201)
        expense_id = create_res.json()["id"]
        del_res = self.client.delete(
            f"/api/direct-expenses/{expense_id}", headers=self._auth(self.a)
        )
        self.assertEqual(del_res.status_code, 204)

    def test_delete_by_non_creator_forbidden(self):
        create_res = self.client.post(
            "/api/direct-expenses",
            json={
                "title": "Dinner",
                "amount": "20.00",
                "paid_by": self.a.id,
                "split_type": "EQUAL",
                "participant_ids": [self.a.id, self.b.id],
            },
            headers=self._auth(self.a),
        )
        self.assertEqual(create_res.status_code, 201)
        expense_id = create_res.json()["id"]
        del_res = self.client.delete(
            f"/api/direct-expenses/{expense_id}", headers=self._auth(self.b)
        )
        self.assertEqual(del_res.status_code, 403)

    def test_delete_nonexistent_returns_404(self):
        res = self.client.delete(
            "/api/direct-expenses/nonexistent", headers=self._auth(self.a)
        )
        self.assertEqual(res.status_code, 404)
