import os
import sys
import unittest
from decimal import Decimal
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-expense-edit")
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
from app.models.user import User
from app.routers.settlements import _compute_balances
from app.services.settlement import net_balances_by_group


class ExpenseEditTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self.db = self.Session()

        self.a = User(phone_number="+15550000001", username="A")
        self.b = User(phone_number="+15550000002", username="B")
        self.c = User(phone_number="+15550000003", username="C")
        self.db.add_all([self.a, self.b, self.c])
        self.db.flush()
        self.group = Group(name="Trip", created_by=self.a.id, invite_token="tok-edit")
        self.db.add(self.group)
        self.db.flush()
        self.db.add_all([
            Membership(group_id=self.group.id, user_id=u.id)
            for u in (self.a, self.b, self.c)
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

    def _add_expense(self, user, amount="30.00", paid_by=None):
        res = self.client.post(
            f"/api/groups/{self.group.id}/expenses/",
            json={
                "title": "Dinner",
                "amount": amount,
                "paid_by": paid_by or user.id,
                "split_type": "EQUAL",
            },
            headers=self._auth(user),
        )
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def test_edit_replaces_amount_payer_and_splits(self):
        expense = self._add_expense(self.a)
        res = self.client.put(
            f"/api/groups/{self.group.id}/expenses/{expense['id']}",
            json={
                "title": "Dinner (fixed)",
                "amount": "60.00",
                "paid_by": self.b.id,
                "split_type": "CUSTOM",
                "splits": [
                    {"user_id": self.a.id, "amount": "10.00"},
                    {"user_id": self.b.id, "amount": "20.00"},
                    {"user_id": self.c.id, "amount": "30.00"},
                ],
            },
            headers=self._auth(self.a),
        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["title"], "Dinner (fixed)")
        self.assertEqual(body["amount"], 60.0)
        self.assertEqual(body["paid_by"], self.b.id)
        self.assertEqual(len(body["splits"]), 3)
        self.assertEqual(
            sorted(s["amount"] for s in body["splits"]), [10.0, 20.0, 30.0]
        )

    def test_edit_rejects_splits_that_do_not_sum_to_total(self):
        expense = self._add_expense(self.a)
        res = self.client.put(
            f"/api/groups/{self.group.id}/expenses/{expense['id']}",
            json={
                "title": "Dinner",
                "amount": "60.00",
                "paid_by": self.a.id,
                "split_type": "CUSTOM",
                "splits": [
                    {"user_id": self.a.id, "amount": "10.00"},
                    {"user_id": self.b.id, "amount": "10.00"},
                    {"user_id": self.c.id, "amount": "10.00"},
                ],
            },
            headers=self._auth(self.a),
        )
        self.assertEqual(res.status_code, 400)

    def test_edit_forbidden_for_other_member(self):
        expense = self._add_expense(self.b, paid_by=self.b.id)
        res = self.client.put(
            f"/api/groups/{self.group.id}/expenses/{expense['id']}",
            json={
                "title": "Nope",
                "amount": "5.00",
                "paid_by": self.c.id,
                "split_type": "EQUAL",
            },
            headers=self._auth(self.c),
        )
        self.assertEqual(res.status_code, 403)

    def test_edit_blocked_once_group_is_settled(self):
        expense = self._add_expense(self.a)
        self.client.post(
            f"/api/groups/{self.group.id}/settlements/confirm",
            headers=self._auth(self.a),
        )
        res = self.client.put(
            f"/api/groups/{self.group.id}/expenses/{expense['id']}",
            json={
                "title": "Late edit",
                "amount": "5.00",
                "paid_by": self.a.id,
                "split_type": "EQUAL",
            },
            headers=self._auth(self.a),
        )
        self.assertEqual(res.status_code, 400)

    def test_my_balance_matches_group_balances(self):
        self._add_expense(self.a, amount="30.00")
        self._add_expense(self.b, amount="10.00", paid_by=self.b.id)

        group_balances = _compute_balances(self.db, self.group.id)
        for user in (self.a, self.b, self.c):
            batched = net_balances_by_group(self.db, user.id, [self.group.id])
            self.assertEqual(
                batched[self.group.id],
                group_balances[user.id].quantize(Decimal("0.01")),
                f"balance mismatch for {user.username}",
            )

    def test_group_list_reports_my_balance(self):
        self._add_expense(self.a, amount="30.00")
        res = self.client.get("/api/groups/", headers=self._auth(self.c))
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()[0]["my_balance"], -10.0)


if __name__ == "__main__":
    unittest.main()
