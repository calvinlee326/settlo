import jwt

from app.core.config import settings

GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = frozenset({"accounts.google.com", "https://accounts.google.com"})
# PyJWKClient caches Google's signing keys, so verification does not fetch per request.
_google_keys = jwt.PyJWKClient(GOOGLE_CERTS_URL)


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
