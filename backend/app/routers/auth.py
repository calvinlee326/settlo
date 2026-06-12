from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    get_token,
)
from app.database import get_db
from app.models.user import TokenBlacklist, User
from app.schemas.user import (
    AccessTokenResponse,
    LogoutRequest,
    RefreshRequest,
    SendOTPRequest,
    SendOTPResponse,
    SetUsernameRequest,
    TokenResponse,
    UserOut,
    VerifyOTPRequest,
)
from app.services.otp import (
    OTPDeliveryError,
    OTPInvalidError,
    OTPLockedError,
    generate_otp,
    verify_otp,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
_otp_ip_attempts: dict[str, deque[datetime]] = defaultdict(deque)


def _check_otp_ip_limit(request: Request) -> None:
    ip_address = request.client.host if request.client else "unknown"
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now - timedelta(minutes=settings.OTP_SEND_WINDOW_MINUTES)
    attempts = _otp_ip_attempts[ip_address]
    while attempts and attempts[0] < cutoff:
        attempts.popleft()
    if len(attempts) >= settings.OTP_IP_SEND_LIMIT:
        raise OTPLockedError(
            "Too many verification codes requested. Try again later."
        )
    attempts.append(now)


def _blacklist(db: Session, token: str) -> None:
    try:
        payload = decode_token(token)
        expired_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc).replace(
            tzinfo=None
        )
    except HTTPException:
        return
    exists = db.query(TokenBlacklist).filter(TokenBlacklist.token == token).first()
    if not exists:
        db.add(TokenBlacklist(token=token, expired_at=expired_at))


@router.post("/send-otp", response_model=SendOTPResponse)
def send_otp(
    body: SendOTPRequest, request: Request, db: Session = Depends(get_db)
):
    try:
        _check_otp_ip_limit(request)
        generate_otp(db, body.phone_number)
    except OTPLockedError as exc:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=str(exc))
    except OTPDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    return SendOTPResponse(
        message="OTP sent", expires_in=settings.OTP_EXPIRE_MINUTES * 60
    )


@router.post("/verify-otp", response_model=TokenResponse)
def verify_otp_endpoint(body: VerifyOTPRequest, db: Session = Depends(get_db)):
    try:
        verify_otp(db, body.phone_number, body.code)
    except OTPLockedError as exc:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=str(exc))
    except OTPDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    except OTPInvalidError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    user = db.query(User).filter(User.phone_number == body.phone_number).first()
    if user is None:
        user = User(phone_number=body.phone_number)
        db.add(user)
        db.commit()
        db.refresh(user)

    is_new_user = user.username is None
    return TokenResponse(
        is_new_user=is_new_user,
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        user=UserOut.model_validate(user),
    )


@router.post("/set-username", response_model=UserOut)
def set_username(
    body: SetUsernameRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.username = body.username.strip()
    db.commit()
    db.refresh(current_user)
    return UserOut.model_validate(current_user)


@router.post("/logout")
def logout(
    body: LogoutRequest | None = None,
    token: str = Depends(get_token),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _blacklist(db, token)
    if body and body.refresh_token:
        _blacklist(db, body.refresh_token)
    db.commit()
    return {"message": "Logged out"}


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
        )
    blacklisted = (
        db.query(TokenBlacklist)
        .filter(TokenBlacklist.token == body.refresh_token)
        .first()
    )
    if blacklisted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked"
        )
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return AccessTokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)
