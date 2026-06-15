import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import OTPCode

logger = logging.getLogger("settlo.otp")
TWILIO_OTP_MARKER = "twilio"


class OTPError(Exception):
    pass


class OTPLockedError(OTPError):
    pass


class OTPInvalidError(OTPError):
    pass


class OTPDeliveryError(OTPError):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _is_send_limited(db: Session, phone_number: str) -> bool:
    now = _utcnow()
    sent_count = (
        db.query(OTPCode)
        .filter(
            OTPCode.phone_number == phone_number,
            OTPCode.created_at >= now - timedelta(minutes=settings.OTP_SEND_WINDOW_MINUTES),
        )
        .count()
    )
    return sent_count >= settings.OTP_SEND_LIMIT


def _twilio_verify_service():
    if not (
        settings.TWILIO_ACCOUNT_SID
        and settings.TWILIO_AUTH_TOKEN
        and settings.TWILIO_VERIFY_SERVICE_SID
    ):
        raise OTPDeliveryError("Twilio Verify is not configured")

    try:
        from twilio.rest import Client
    except ImportError as exc:
        raise OTPDeliveryError("Twilio Verify dependency is not installed") from exc

    return Client(
        settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN
    ).verify.v2.services(settings.TWILIO_VERIFY_SERVICE_SID)


def _twilio_error_types():
    try:
        from twilio.base.exceptions import TwilioRestException
    except ImportError:
        return ()

    return (TwilioRestException,)


def _start_twilio_verification(phone_number: str) -> None:
    try:
        _twilio_verify_service().verifications.create(
            to=phone_number, channel=settings.TWILIO_VERIFY_CHANNEL
        )
    except OTPDeliveryError:
        raise
    except _twilio_error_types() as exc:
        raise OTPDeliveryError("OTP delivery failed") from exc


def _check_twilio_verification(phone_number: str, code: str) -> str:
    try:
        check = _twilio_verify_service().verification_checks.create(
            to=phone_number, code=code
        )
    except OTPDeliveryError:
        raise
    except _twilio_error_types() as exc:
        if getattr(exc, "status", None) == 404:
            raise OTPInvalidError(
                "OTP not found or expired. Request a new code."
            ) from exc
        raise OTPDeliveryError("OTP verification failed") from exc

    return check.status


def generate_otp(db: Session, phone_number: str) -> OTPCode:
    if _is_send_limited(db, phone_number):
        raise OTPLockedError(
            "Too many verification codes requested. Try again later."
        )

    now = _utcnow()
    otp = OTPCode(
        phone_number=phone_number,
        code=TWILIO_OTP_MARKER,
        expired_at=now + timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
        is_used=True,
        created_at=now,
    )

    try:
        db.add(otp)
        db.flush()
        if not settings.DEV_OTP_CODE:
            _start_twilio_verification(phone_number)
        db.commit()
    except Exception:
        db.rollback()
        raise

    if settings.DEV_OTP_CODE:
        logger.warning(
            "DEV_OTP_CODE active: Twilio bypassed, use the fixed dev code to log in"
        )
    logger.info("OTP sent for phone ending in %s", phone_number[-4:])
    return otp


def verify_otp(db: Session, phone_number: str, code: str) -> None:
    if settings.DEV_OTP_CODE:
        if code != settings.DEV_OTP_CODE:
            raise OTPInvalidError("Invalid OTP code.")
        return
    if _check_twilio_verification(phone_number, code) != "approved":
        raise OTPInvalidError("Invalid OTP code.")
