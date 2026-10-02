import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


# 3-30 of a-z 0-9 _ . with no leading/trailing period and no "..", like Instagram.
# At least one letter, so an ID can never be mistaken for a phone number.
HANDLE_PATTERN = re.compile(r"^(?=.*[a-z])(?!.*\.\.)[a-z0-9_][a-z0-9_.]{1,28}[a-z0-9_]$")


def normalize_handle(value: str) -> str:
    """Handles are case-insensitive: store and compare them lowercase, without "@"."""
    handle = value.strip().removeprefix("@").lower()
    if not HANDLE_PATTERN.fullmatch(handle):
        raise ValueError(
            "ID must be 3-30 letters, numbers, underscores or periods, with at least "
            "one letter and no period at the start, at the end, or twice in a row"
        )
    return handle


class GoogleAuthRequest(BaseModel):
    credential: str = Field(min_length=1, max_length=4096)


class SetHandleRequest(BaseModel):
    handle: str

    @field_validator("handle")
    @classmethod
    def _normalize_handle(cls, value: str) -> str:
        return normalize_handle(value)


class HandleAvailability(BaseModel):
    handle: str
    available: bool
    message: str | None = None


class UserLookup(BaseModel):
    handle: str

    @field_validator("handle")
    @classmethod
    def _normalize_handle(cls, value: str) -> str:
        return normalize_handle(value)


class SetUsernameRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str | None
    google_linked: bool
    username: str | None
    handle: str | None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
