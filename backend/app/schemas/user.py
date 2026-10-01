import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def normalize_us_phone(value: str) -> str:
    """Normalize any US phone format to E.164 (+1XXXXXXXXXX).

    Accepts "9099082966", "19099082966", "+1 (909) 908-2966", etc.
    US-only for now.
    """
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        raise ValueError("Enter a valid 10-digit US phone number")
    return f"+1{digits}"


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


class SendOTPRequest(BaseModel):
    phone_number: str

    @field_validator("phone_number")
    @classmethod
    def _normalize_phone(cls, value: str) -> str:
        return normalize_us_phone(value)


class SendOTPResponse(BaseModel):
    message: str
    expires_in: int


class VerifyOTPRequest(BaseModel):
    phone_number: str
    code: str = Field(pattern=r"^[0-9]{6}$")

    @field_validator("phone_number")
    @classmethod
    def _normalize_phone(cls, value: str) -> str:
        return normalize_us_phone(value)


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
    """Find a user by ID or by phone number; exactly one must be given."""

    phone_number: str | None = Field(default=None, min_length=3, max_length=20)
    handle: str | None = None

    @field_validator("handle")
    @classmethod
    def _normalize_handle(cls, value: str | None) -> str | None:
        return None if value is None else normalize_handle(value)

    @model_validator(mode="after")
    def _exactly_one(self) -> "UserLookup":
        if (self.phone_number is None) == (self.handle is None):
            raise ValueError("Provide either an ID or a phone number")
        return self


class SetUsernameRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    phone_number: str | None
    email: str | None
    google_linked: bool
    username: str | None
    handle: str | None
    created_at: datetime


class TokenResponse(BaseModel):
    is_new_user: bool
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
