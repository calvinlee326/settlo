import os
import sys
import unittest
import importlib
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-public-readiness")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.schema import MetaData

from app.core.config import Settings
from app.database import Base, database_url_for_sqlalchemy
from app.models import *  # noqa: F401,F403
from app.models.expense import Expense, ExpenseSplit, Settlement, SplitType
from app.models.group import Group, Membership
from app.models.user import OTPCode, User
from app.routers import auth as auth_router
from app.routers.groups import _group_detail, remove_member
from app.routers.settlements import get_settlements, mark_paid
from app.schemas.user import SendOTPRequest
from app.services import otp as otp_service


class PublicReadinessTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def create_group_with_members(self):
        creator = User(phone_number="+15550000001", username="Creator")
        member = User(phone_number="+15550000002", username="Member")
        self.db.add_all([creator, member])
        self.db.flush()

        group = Group(name="Trip", created_by=creator.id)
        self.db.add(group)
        self.db.flush()
        self.db.add_all(
            [
                Membership(user_id=creator.id, group_id=group.id),
                Membership(user_id=member.id, group_id=group.id),
            ]
        )
        self.db.commit()
        return creator, member, group

    def create_expense(self, group, payer, creator, splits):
        expense = Expense(
            group_id=group.id,
            paid_by=payer.id,
            title="Dinner",
            amount=Decimal("100.00"),
            currency="USD",
            split_type=SplitType.CUSTOM,
            created_by=creator.id,
        )
        self.db.add(expense)
        self.db.flush()
        for user, amount in splits:
            self.db.add(
                ExpenseSplit(
                    expense_id=expense.id,
                    user_id=user.id,
                    amount=Decimal(amount),
                )
            )
        self.db.commit()
        return expense

    def test_member_detail_does_not_expose_phone_numbers(self):
        creator, member, group = self.create_group_with_members()

        detail = _group_detail(self.db, group)

        member_payloads = [m.model_dump() for m in detail.members]
        self.assertNotIn("phone_number", member_payloads[0])
        self.assertEqual(
            {m["id"] for m in member_payloads}, {creator.id, member.id}
        )

    def test_member_with_financial_activity_cannot_be_removed(self):
        creator, member, group = self.create_group_with_members()
        self.create_expense(
            group,
            payer=creator,
            creator=creator,
            splits=[(creator, "50.00"), (member, "50.00")],
        )

        with self.assertRaises(HTTPException) as exc:
            remove_member(group.id, member.id, current_user=creator, db=self.db)

        self.assertEqual(exc.exception.status_code, 400)
        membership = (
            self.db.query(Membership)
            .filter(Membership.group_id == group.id, Membership.user_id == member.id)
            .first()
        )
        self.assertIsNotNone(membership)

    def test_get_settlements_does_not_persist_unpaid_settlements(self):
        creator, member, group = self.create_group_with_members()
        self.create_expense(
            group,
            payer=creator,
            creator=creator,
            splits=[(creator, "50.00"), (member, "50.00")],
        )

        result = get_settlements(group.id, current_user=creator, db=self.db)

        self.assertEqual(self.db.query(Settlement).count(), 0)
        self.assertEqual(len(result.settlements), 1)
        self.assertEqual(result.settlements[0].from_user, member.id)
        self.assertEqual(result.settlements[0].to_user, creator.id)
        self.assertEqual(result.settlements[0].amount, 50.0)

    def test_mark_paid_persists_computed_settlement(self):
        creator, member, group = self.create_group_with_members()
        self.create_expense(
            group,
            payer=creator,
            creator=creator,
            splits=[(creator, "50.00"), (member, "50.00")],
        )
        draft = get_settlements(group.id, current_user=creator, db=self.db).settlements[0]

        paid = mark_paid(group.id, draft.id, current_user=member, db=self.db)

        self.assertTrue(paid.is_paid)
        self.assertEqual(paid.from_user, member.id)
        self.assertEqual(paid.to_user, creator.id)
        self.assertEqual(self.db.query(Settlement).count(), 1)

    def test_secret_key_must_be_configured(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValidationError):
                Settings(_env_file=None)

    def test_backend_has_postgres_and_twilio_dependencies(self):
        requirements = Path(__file__).resolve().parents[1] / "requirements.txt"
        text = requirements.read_text()

        self.assertIn("psycopg[binary]", text)
        self.assertIn("twilio", text)

    def test_plain_postgres_database_url_uses_psycopg_driver(self):
        self.assertEqual(
            database_url_for_sqlalchemy("postgresql://user:pass@host:5432/db"),
            "postgresql+psycopg://user:pass@host:5432/db",
        )
        self.assertEqual(
            database_url_for_sqlalchemy("postgres://user:pass@host:5432/db"),
            "postgresql+psycopg://user:pass@host:5432/db",
        )

    def test_app_import_does_not_create_tables(self):
        existing = sys.modules.pop("app.main", None)
        try:
            with patch.object(
                MetaData, "create_all", side_effect=AssertionError("create_all called")
            ):
                importlib.import_module("app.main")
        finally:
            sys.modules.pop("app.main", None)
            if existing is not None:
                sys.modules["app.main"] = existing

    def test_local_otp_catcher_is_not_shipped(self):
        catcher = Path(__file__).resolve().parents[1] / "otp_catcher.py"

        self.assertFalse(catcher.exists())

    def test_generate_otp_is_rate_limited_and_does_not_print_code(self):
        phone_number = "+15550000003"

        class Verifications:
            def __init__(self):
                self.calls = []

            def create(self, **kwargs):
                self.calls.append(kwargs)
                return SimpleNamespace(status="pending")

        class VerifyService:
            def __init__(self):
                self.verifications = Verifications()

        service = VerifyService()

        with (
            patch.object(otp_service.settings, "OTP_SEND_LIMIT", 2),
            patch.object(otp_service.settings, "OTP_SEND_WINDOW_MINUTES", 10),
            patch.object(otp_service, "_twilio_verify_service", return_value=service),
            patch("builtins.print") as print_mock,
        ):
            otp_service.generate_otp(self.db, phone_number)
            otp_service.generate_otp(self.db, phone_number)
            with self.assertRaises(otp_service.OTPLockedError):
                otp_service.generate_otp(self.db, phone_number)

        self.assertEqual(
            self.db.query(OTPCode).filter(OTPCode.phone_number == phone_number).count(),
            2,
        )
        self.assertEqual(len(service.verifications.calls), 2)
        print_mock.assert_not_called()

    def test_generate_otp_uses_twilio_verify(self):
        phone_number = "+15550000005"

        class Verifications:
            def __init__(self):
                self.calls = []

            def create(self, **kwargs):
                self.calls.append(kwargs)
                return SimpleNamespace(status="pending")

        class VerifyService:
            def __init__(self):
                self.verifications = Verifications()

        service = VerifyService()

        with (
            patch.object(
                otp_service, "_twilio_verify_service", return_value=service, create=True
            ),
        ):
            otp_service.generate_otp(self.db, phone_number)

        self.assertEqual(
            service.verifications.calls, [{"to": phone_number, "channel": "sms"}]
        )
        saved = (
            self.db.query(OTPCode)
            .filter(OTPCode.phone_number == phone_number)
            .one()
        )
        self.assertEqual(saved.code, "twilio")

    def test_verify_otp_uses_twilio_verify(self):
        phone_number = "+15550000006"

        class VerificationChecks:
            def __init__(self):
                self.calls = []

            def create(self, **kwargs):
                self.calls.append(kwargs)
                return SimpleNamespace(status="approved")

        class VerifyService:
            def __init__(self):
                self.verification_checks = VerificationChecks()

        service = VerifyService()

        with patch.object(
            otp_service, "_twilio_verify_service", return_value=service, create=True
        ):
            rejected = False
            try:
                otp_service.verify_otp(self.db, phone_number, "123456")
            except otp_service.OTPInvalidError:
                rejected = True

        self.assertFalse(rejected)
        self.assertEqual(
            service.verification_checks.calls,
            [{"to": phone_number, "code": "123456"}],
        )

    def test_verify_otp_rejects_unapproved_twilio_status(self):
        phone_number = "+15550000007"

        class VerificationChecks:
            def __init__(self):
                self.calls = []

            def create(self, **kwargs):
                self.calls.append(kwargs)
                return SimpleNamespace(status="pending")

        class VerifyService:
            def __init__(self):
                self.verification_checks = VerificationChecks()

        service = VerifyService()

        with (
            patch.object(
                otp_service, "_twilio_verify_service", return_value=service, create=True
            ),
            self.assertRaises(otp_service.OTPInvalidError),
        ):
            otp_service.verify_otp(self.db, phone_number, "123456")

        self.assertEqual(
            service.verification_checks.calls,
            [{"to": phone_number, "code": "123456"}],
        )

    def test_verify_otp_treats_missing_twilio_challenge_as_invalid(self):
        phone_number = "+15550000008"

        class TwilioNotFoundError(Exception):
            status = 404

        class VerificationChecks:
            def create(self, **kwargs):
                raise TwilioNotFoundError()

        class VerifyService:
            verification_checks = VerificationChecks()

        with (
            patch.object(
                otp_service, "_twilio_verify_service", return_value=VerifyService()
            ),
            patch.object(
                otp_service, "_twilio_error_types", return_value=(TwilioNotFoundError,)
            ),
            self.assertRaises(otp_service.OTPInvalidError),
        ):
            otp_service.verify_otp(self.db, phone_number, "123456")

    def test_send_otp_is_rate_limited_by_ip(self):
        class Client:
            host = "203.0.113.10"

        class Request:
            client = Client()

        auth_router._otp_ip_attempts.clear()
        body = SendOTPRequest(phone_number="+15550000004")

        with (
            patch.object(auth_router.settings, "OTP_IP_SEND_LIMIT", 2),
            patch.object(auth_router.settings, "OTP_SEND_WINDOW_MINUTES", 10),
            patch.object(auth_router, "generate_otp", return_value=None),
        ):
            auth_router.send_otp(body, Request(), self.db)
            auth_router.send_otp(body, Request(), self.db)
            with self.assertRaises(HTTPException) as exc:
                auth_router.send_otp(body, Request(), self.db)

        self.assertEqual(exc.exception.status_code, 423)
        auth_router._otp_ip_attempts.clear()


if __name__ == "__main__":
    unittest.main()
