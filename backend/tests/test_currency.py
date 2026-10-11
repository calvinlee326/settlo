import io
import json
import os
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-currency-tests")
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
from app.models.user import User
from app.services import fx
from app.services.settlement import equal_split

RATES = {
    "USD": Decimal("1"), "TWD": Decimal("31.959582"), "JPY": Decimal("158.287265"),
    "CNY": Decimal("6.706851"), "KRW": Decimal("1341.69027"), "THB": Decimal("33.5671"),
    "EUR": Decimal("0.892438"),
}


class SharesToUsdTest(unittest.TestCase):
    def test_converted_shares_add_up_to_converted_total(self):
        shares = [Decimal("333.34"), Decimal("333.33"), Decimal("333.33")]
        rate = RATES["JPY"]
        self.assertEqual(sum(fx.shares_to_usd(shares, rate)), fx.to_usd(Decimal("1000"), rate))

    def test_fetched_rates_match_stored_precision(self):
        payload = {"result": "success", "rates": {**{c: 1 for c in RATES}, "EUR": 0.89243812}}
        body = io.BytesIO(json.dumps(payload).encode())
        with patch("app.services.fx.urllib.request.urlopen", return_value=body):
            self.assertEqual(fx._fetch_rates()[0]["EUR"], Decimal("0.892438"))

    def test_rates_kept_until_provider_publishes_new_ones(self):
        fx._cached = None
        with patch("app.services.fx._fetch_rates", return_value=(dict(RATES), 50_000.0)) as fetch, \
                patch("app.services.fx.time.time", side_effect=[1_000.0, 49_999.0, 50_001.0]):
            for _ in range(3):
                fx.usd_rates()
        fx._cached = None
        self.assertEqual(fetch.call_count, 2)


class WholeUnitSplitTest(unittest.TestCase):
    def test_yen_splits_into_whole_yen(self):
        shares = [a for _, a in equal_split(Decimal("1000"), ["a", "b", "c"], fx.currency_unit("JPY"))]
        self.assertEqual(shares, [Decimal("334"), Decimal("333"), Decimal("333")])

    def test_legacy_fractional_yen_still_adds_up(self):
        shares = [a for _, a in equal_split(Decimal("1000.50"), ["a", "b", "c"], fx.currency_unit("JPY"))]
        self.assertEqual(sum(shares), Decimal("1000.50"))


class CurrencyApiTest(unittest.TestCase):
    def setUp(self):
        fx._cached = None
        self.fetch = patch("app.services.fx._fetch_rates", return_value=(dict(RATES), 0))
        self.fetch.start()

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
        self.group = Group(name="Tokyo", created_by=self.a.id, invite_token="tok-fx")
        self.db.add(self.group)
        self.db.flush()
        self.db.add_all([
            Membership(group_id=self.group.id, user_id=u.id) for u in (self.a, self.b, self.c)
        ])
        self.db.add(Friendship(
            requester_id=self.a.id, addressee_id=self.b.id, status=FriendshipStatus.ACCEPTED
        ))
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
        self.fetch.stop()
        fx._cached = None
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def _auth(self, user):
        return {"Authorization": f"Bearer {create_access_token(user.id)}"}

    def _add(self, amount, currency):
        return self.client.post(
            f"/api/groups/{self.group.id}/expenses/",
            json={"title": "Ramen", "amount": amount, "currency": currency,
                  "paid_by": self.a.id, "split_type": "EQUAL"},
            headers=self._auth(self.a),
        )

    def test_expense_locks_rate_and_usd_value(self):
        res = self._add("1000.00", "JPY")
        self.assertEqual(res.status_code, 201, res.text)
        body = res.json()
        self.assertEqual(
            (body["currency"], body["fx_rate"], body["amount_usd"]), ("JPY", 158.287265, 6.32)
        )

    def test_foreign_expense_settles_to_zero_and_archives(self):
        self._add("1000.00", "JPY")
        self._add("10.00", "USD")
        data = self.client.get(
            f"/api/groups/{self.group.id}/settlements/", headers=self._auth(self.a)
        ).json()
        for s in data["settlements"]:
            payer = self.b if s["from_user"] == self.b.id else self.c
            res = self.client.post(
                f"/api/groups/{self.group.id}/settlements/{s['id']}/pay",
                headers=self._auth(payer),
            )
            self.assertEqual(res.status_code, 200, res.text)
        res = self.client.post(
            f"/api/groups/{self.group.id}/settlements/confirm", headers=self._auth(self.a)
        )
        self.assertEqual(res.status_code, 200, res.text)

    def test_edit_keeps_rate_from_when_expense_was_added(self):
        expense = self._add("1000.00", "JPY").json()
        self.fetch.stop()
        fx._cached = None
        with patch("app.services.fx._fetch_rates", return_value=({**RATES, "JPY": Decimal("100")}, 0)):
            res = self.client.put(
                f"/api/groups/{self.group.id}/expenses/{expense['id']}",
                json={"title": "Ramen", "amount": "2000.00", "currency": "JPY",
                      "paid_by": self.a.id, "split_type": "EQUAL"},
                headers=self._auth(self.a),
            )
        self.fetch.start()
        self.assertEqual(res.json()["amount_usd"], 12.64)

    def test_fractional_yen_rejected(self):
        self.assertEqual(self._add("1000.50", "JPY").status_code, 400)

    def test_edit_without_currency_change_skips_rate_fetch(self):
        expense = self._add("1000.00", "JPY").json()
        fx._cached = None
        with patch("app.services.fx._fetch_rates", side_effect=OSError("down")):
            res = self.client.put(
                f"/api/groups/{self.group.id}/expenses/{expense['id']}",
                json={"title": "Ramen", "amount": "1200.00", "currency": "JPY",
                      "paid_by": self.a.id, "split_type": "EQUAL"},
                headers=self._auth(self.a),
            )
        self.assertEqual(res.status_code, 200, res.text)

    def test_unsupported_currency_rejected(self):
        self.assertEqual(self._add("10.00", "GBP").status_code, 422)

    def test_rates_unavailable_returns_503(self):
        with patch("app.services.fx._fetch_rates", side_effect=OSError("down")):
            self.assertEqual(self._add("10.00", "TWD").status_code, 503)

    def test_direct_expense_balance_is_in_usd(self):
        self.client.post(
            "/api/direct-expenses",
            json={"title": "Taxi", "amount": "639.19", "currency": "TWD",
                  "paid_by": self.a.id, "participant_ids": [self.a.id, self.b.id]},
            headers=self._auth(self.a),
        )
        friends = self.client.get("/api/friends", headers=self._auth(self.a)).json()
        self.assertEqual(friends[0]["net_balance"], 10.0)

    def test_rates_endpoint_lists_supported_currencies(self):
        res = self.client.get("/api/rates", headers=self._auth(self.a))
        self.assertEqual(set(res.json()["rates"]), set(fx.SUPPORTED_CURRENCIES))


if __name__ == "__main__":
    unittest.main()
