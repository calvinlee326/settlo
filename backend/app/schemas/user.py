import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class SetUsernameRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    phone_number: str
    username: str | None
    created_at: datetime


class TokenResponse(BaseModel):
    is_new_user: bool
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
