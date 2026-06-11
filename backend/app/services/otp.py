import logging
import secrets
from datetime import datetime, timedelta

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


def _is_locked(db: Session, phone_number: str) -> bool:
    now = datetime.utcnow()
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


def generate_otp(db: Session, phone_number: str) -> OTPCode:
    if _is_locked(db, phone_number):
        raise OTPLockedError(
            "Too many failed attempts. Try again in 10 minutes."
        )

    # Invalidate previous unused codes for this phone number
    db.query(OTPCode).filter(
        OTPCode.phone_number == phone_number, OTPCode.is_used.is_(False)
    ).update({OTPCode.is_used: True})

    code = f"{secrets.randbelow(1000000):06d}"
    now = datetime.utcnow()
    otp = OTPCode(
        phone_number=phone_number,
        code=code,
        expired_at=now + timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
        created_at=now,
    )
    db.add(otp)
    db.commit()

    # Development only: print OTP to terminal instead of sending SMS
    message = f"[Settlo OTP] phone={phone_number} code={code} (expires in {settings.OTP_EXPIRE_MINUTES} min)"
    logger.info(message)
    print(message, flush=True)
    return otp


def verify_otp(db: Session, phone_number: str, code: str) -> None:
    if _is_locked(db, phone_number):
        raise OTPLockedError(
            "Too many failed attempts. Try again in 10 minutes."
        )

    now = datetime.utcnow()
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
