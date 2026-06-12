import logging
import secrets
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from json import dumps

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import OTPCode

logger = logging.getLogger("settlo.otp")


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


def _is_locked(db: Session, phone_number: str) -> bool:
    now = _utcnow()
    locked = (
        db.query(OTPCode)
        .filter(
            OTPCode.phone_number == phone_number,
            OTPCode.failed_attempts >= settings.OTP_MAX_ATTEMPTS,
            OTPCode.created_at >= now - timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
        )
        .first()
    )
    return locked is not None


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


def _deliver_otp(phone_number: str, code: str) -> None:
    url = (settings.OTP_DELIVERY_WEBHOOK_URL or "").strip()
    if not url:
        raise OTPDeliveryError("OTP delivery is not configured")

    payload = dumps({"phone_number": phone_number, "code": code}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            request, timeout=settings.OTP_DELIVERY_TIMEOUT_SECONDS
        ) as response:
            if response.status >= 400:
                raise OTPDeliveryError("OTP delivery failed")
    except (TimeoutError, urllib.error.URLError) as exc:
        raise OTPDeliveryError("OTP delivery failed") from exc


def generate_otp(db: Session, phone_number: str) -> OTPCode:
    if _is_locked(db, phone_number):
        raise OTPLockedError(
            "Too many failed attempts. Try again in 10 minutes."
        )
    if _is_send_limited(db, phone_number):
        raise OTPLockedError(
            "Too many verification codes requested. Try again later."
        )

    code = f"{secrets.randbelow(1000000):06d}"
    now = _utcnow()
    otp = OTPCode(
        phone_number=phone_number,
        code=code,
        expired_at=now + timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
        created_at=now,
    )

    try:
        db.query(OTPCode).filter(
            OTPCode.phone_number == phone_number, OTPCode.is_used.is_(False)
        ).update({OTPCode.is_used: True})
        db.add(otp)
        db.flush()
        _deliver_otp(phone_number, code)
        db.commit()
    except Exception:
        db.rollback()
        raise

    logger.info("OTP sent for phone ending in %s", phone_number[-4:])
    return otp


def verify_otp(db: Session, phone_number: str, code: str) -> None:
    if _is_locked(db, phone_number):
        raise OTPLockedError(
            "Too many failed attempts. Try again in 10 minutes."
        )

    now = _utcnow()
    otp = (
        db.query(OTPCode)
        .filter(
            OTPCode.phone_number == phone_number,
            OTPCode.is_used.is_(False),
            OTPCode.expired_at > now,
        )
        .order_by(OTPCode.created_at.desc())
        .first()
    )
    if otp is None:
        raise OTPInvalidError("OTP not found or expired. Request a new code.")

    if not secrets.compare_digest(otp.code, code):
        otp.failed_attempts += 1
        db.commit()
        if otp.failed_attempts >= settings.OTP_MAX_ATTEMPTS:
            raise OTPLockedError(
                "Too many failed attempts. Try again in 10 minutes."
            )
        raise OTPInvalidError("Invalid OTP code.")

    otp.is_used = True
    db.commit()
