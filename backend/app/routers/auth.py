from collections import deque
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
)
from app.database import get_db
from app.models.user import TokenBlacklist, User
from app.schemas.user import (
    AccessTokenResponse,
    GoogleAuthRequest,
    SendOTPRequest,
    SendOTPResponse,
    SetUsernameRequest,
    TokenResponse,
    UserOut,
    VerifyOTPRequest,
)
from app.services.google_auth import (
    GoogleAuthError,
    GoogleUnavailableError,
    verified_email,
    verify_google_token,
)
from app.services.otp import (
    OTPDeliveryError,
    OTPInvalidError,
    OTPLockedError,
    generate_otp,
    verify_otp,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ponytail: in-process counters, so the limit is per worker and resets on deploy.
# Move to Redis if the backend ever runs more than one instance.
_otp_ip_attempts: dict[str, deque[datetime]] = {}
OTP_IP_SWEEP_THRESHOLD = 1024
REFRESH_COOKIE_NAME = "settlo_refresh"
REFRESH_COOKIE_PATH = "/api/auth"
_AUTH_ORIGINS = frozenset(
    [settings.FRONTEND_URL]
    + [origin.strip() for origin in settings.EXTRA_ORIGINS.split(",") if origin.strip()]
)


def _check_origin(request: Request) -> None:
    if request.headers.get("origin") not in _AUTH_ORIGINS:
        raise HTTPException(status_code=403, detail="Untrusted request origin")


def _check_otp_ip_limit(request: Request) -> None:
    ip_address = request.client.host if request.client else "unknown"
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now - timedelta(minutes=settings.OTP_SEND_WINDOW_MINUTES)

    if len(_otp_ip_attempts) > OTP_IP_SWEEP_THRESHOLD:
        for stale in [
            ip
            for ip, seen in _otp_ip_attempts.items()
            if not seen or seen[-1] < cutoff
        ]:
            del _otp_ip_attempts[stale]

    attempts = _otp_ip_attempts.setdefault(ip_address, deque())
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


def _issue_session(response: Response, user: User) -> TokenResponse:
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        create_refresh_token(user.id),
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        path=REFRESH_COOKIE_PATH,
    )
    return TokenResponse(
        is_new_user=user.username is None,
        access_token=create_access_token(user.id),
        user=UserOut.model_validate(user),
    )


def _google_claims(credential: str) -> dict:
    try:
        return verify_google_token(credential)
    except GoogleUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    except GoogleAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


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
def verify_otp_endpoint(
    body: VerifyOTPRequest, request: Request, response: Response,
    db: Session = Depends(get_db),
):
    _check_origin(request)
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

    return _issue_session(response, user)


@router.post("/google", response_model=TokenResponse)
def google_login(
    body: GoogleAuthRequest, request: Request, response: Response,
    db: Session = Depends(get_db),
):
    _check_origin(request)
    claims = _google_claims(body.credential)
    user = db.query(User).filter(User.google_sub == claims["sub"]).first()
    if user is None:
        name = (claims.get("name") or "").strip()[:50]
        user = User(
            google_sub=claims["sub"],
            email=verified_email(claims),
            username=name or None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return _issue_session(response, user)


@router.post("/google/link", response_model=UserOut)
def link_google(
    body: GoogleAuthRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    claims = _google_claims(body.credential)
    owner = db.query(User).filter(User.google_sub == claims["sub"]).first()
    if owner is not None and owner.id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This Google account is already linked to another Settlo account",
        )
    current_user.google_sub = claims["sub"]
    current_user.email = verified_email(claims)
    db.commit()
    db.refresh(current_user)
    return UserOut.model_validate(current_user)


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
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    _check_origin(request)
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        _blacklist(db, authorization[7:])
    cookie = request.cookies.get(REFRESH_COOKIE_NAME)
    if cookie:
        _blacklist(db, cookie)
    db.commit()
    response.delete_cookie(
        REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH,
        secure=settings.REFRESH_COOKIE_SECURE, httponly=True,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )
    return {"message": "Logged out"}


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(request: Request, db: Session = Depends(get_db)):
    _check_origin(request)
    cookie = request.cookies.get(REFRESH_COOKIE_NAME)
    if not cookie:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(cookie)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
        )
    blacklisted = (
        db.query(TokenBlacklist)
        .filter(TokenBlacklist.token == cookie)
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
