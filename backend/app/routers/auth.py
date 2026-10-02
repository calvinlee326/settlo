from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
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
    GoogleAuthRequest,
    HandleAvailability,
    SetHandleRequest,
    SetUsernameRequest,
    TokenResponse,
    UserOut,
    normalize_handle,
)
from app.services.google_auth import (
    GoogleAuthError,
    GoogleUnavailableError,
    verified_email,
    verify_google_token,
)
from app.services.handles import handle_problem

router = APIRouter(prefix="/api/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "settlo_refresh"
REFRESH_COOKIE_PATH = "/api/auth"
_AUTH_ORIGINS = frozenset(
    [settings.FRONTEND_URL]
    + [origin.strip() for origin in settings.EXTRA_ORIGINS.split(",") if origin.strip()]
)


def _check_origin(request: Request) -> None:
    if request.headers.get("origin") not in _AUTH_ORIGINS:
        raise HTTPException(status_code=403, detail="Untrusted request origin")


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


@router.post("/google", response_model=TokenResponse)
def google_login(
    body: GoogleAuthRequest, request: Request, response: Response,
    db: Session = Depends(get_db),
):
    _check_origin(request)
    claims = _google_claims(body.credential)
    user = db.query(User).filter(User.google_sub == claims["sub"]).first()
    if user is None:
        email = verified_email(claims)
        name = (claims.get("name") or (email or "").split("@")[0]).strip()[:50]
        user = User(google_sub=claims["sub"], email=email, username=name or None)
        db.add(user)
        db.commit()
        db.refresh(user)
    return _issue_session(response, user)


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


@router.get("/handle-available", response_model=HandleAvailability)
def handle_available(
    handle: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        normalized = normalize_handle(handle)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        )
    problem = handle_problem(db, normalized, current_user.id)
    return HandleAvailability(handle=normalized, available=problem is None, message=problem)


@router.post("/set-handle", response_model=UserOut)
def set_handle(
    body: SetHandleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    problem = handle_problem(db, body.handle, current_user.id)
    if problem:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=problem)
    current_user.handle = body.handle
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That ID is already taken"
        )
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


@router.post("/refresh", response_model=TokenResponse)
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
    return TokenResponse(
        access_token=create_access_token(user.id),
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)
