from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./settlo.db"
    SECRET_KEY: str = Field(min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    OTP_EXPIRE_MINUTES: int = 10
    OTP_SEND_LIMIT: int = 3
    OTP_IP_SEND_LIMIT: int = 20
    OTP_SEND_WINDOW_MINUTES: int = 10
    TWILIO_ACCOUNT_SID: str | None = None
    TWILIO_AUTH_TOKEN: str | None = None
    TWILIO_VERIFY_SERVICE_SID: str | None = None
    TWILIO_VERIFY_CHANNEL: str = "sms"
    FRONTEND_URL: str = "http://localhost:5173"
    EXTRA_ORIGINS: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("SECRET_KEY")
    @classmethod
    def _reject_placeholder_secret(cls, value: str) -> str:
        if value in {"change-this-secret-key", "change-this-to-a-long-random-string"}:
            raise ValueError("SECRET_KEY must be changed before startup")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
