from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SendOTPRequest(BaseModel):
    phone_number: str = Field(pattern=r"^\+?[0-9]{7,15}$")


class SendOTPResponse(BaseModel):
    message: str
    expires_in: int


class VerifyOTPRequest(BaseModel):
    phone_number: str = Field(pattern=r"^\+?[0-9]{7,15}$")
    code: str = Field(pattern=r"^[0-9]{6}$")


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
