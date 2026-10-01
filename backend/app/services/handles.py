from sqlalchemy.orm import Session

from app.models.user import User

# Names that would let someone pose as Settlo or as a system page.
RESERVED_HANDLES = frozenset({
    "about", "admin", "administrator", "api", "billing", "contact", "help",
    "info", "login", "logout", "me", "mod", "moderator", "null", "official",
    "privacy", "root", "security", "settings", "signup", "staff", "support",
    "system", "team", "terms", "undefined", "verify", "www",
})
BRAND_NAME = "settlo"


def handle_problem(db: Session, handle: str, user_id: str) -> str | None:
    """Why `user_id` cannot take this (already normalized) handle, or None if it can."""
    if handle in RESERVED_HANDLES or BRAND_NAME in handle:
        return "That ID is reserved"
    owner = db.query(User.id).filter(User.handle == handle).first()
    if owner is not None and owner.id != user_id:
        return "That ID is already taken"
    return None
