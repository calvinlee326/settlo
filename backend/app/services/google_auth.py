import jwt
from sqlalchemy import exists, or_
from sqlalchemy.orm import Session

import app.models  # noqa: F401  registers every table that can reference a user
from app.core.config import settings
from app.database import Base
from app.models.user import User

GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = frozenset({"accounts.google.com", "https://accounts.google.com"})
# PyJWKClient caches Google's signing keys, so verification does not fetch per request.
_google_keys = jwt.PyJWKClient(GOOGLE_CERTS_URL)
_USER_REFERENCES = tuple(
    fk.parent
    for table in Base.metadata.sorted_tables
    for fk in table.foreign_keys
    if fk.target_fullname == "users.id"
)


class GoogleAuthError(Exception):
    pass


class GoogleUnavailableError(Exception):
    pass


def verify_google_token(credential: str) -> dict:
    """Verify a Google Identity Services ID token and return its claims."""
    if not settings.GOOGLE_CLIENT_ID:
        raise GoogleUnavailableError("Google sign-in is not configured")
    try:
        key = _google_keys.get_signing_key_from_jwt(credential).key
        claims = jwt.decode(
            credential,
            key,
            algorithms=["RS256"],
            audience=settings.GOOGLE_CLIENT_ID,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except jwt.PyJWKClientConnectionError as exc:
        raise GoogleUnavailableError("Could not reach Google. Try again.") from exc
    except jwt.PyJWTError as exc:
        raise GoogleAuthError("Invalid Google sign-in") from exc
    if claims["iss"] not in GOOGLE_ISSUERS:
        raise GoogleAuthError("Invalid Google sign-in")
    return claims


def verified_email(claims: dict) -> str | None:
    return claims.get("email") if claims.get("email_verified") else None


def is_unused_google_account(db: Session, user: User) -> bool:
    """True for an account Google sign-in created that nothing references yet.

    A phone user who taps "Continue with Google" before linking gets one of these;
    it is safe to delete so the Google account can move to their phone account.
    """
    if user.phone_number is not None:
        return False
    in_use = or_(*(exists().where(column == user.id) for column in _USER_REFERENCES))
    return not db.query(in_use).scalar()
