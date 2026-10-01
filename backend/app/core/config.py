from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./settlo.db"
    SECRET_KEY: str = Field(min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REFRESH_COOKIE_SECURE: bool = True
    REFRESH_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "none"
    FRONTEND_URL: str = "http://localhost:5173"
    EXTRA_ORIGINS: str = ""
    GOOGLE_CLIENT_ID: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("SECRET_KEY")
    @classmethod
    def _reject_placeholder_secret(cls, value: str) -> str:
        if value in {"change-this-secret-key", "change-this-to-a-long-random-string"}:
            raise ValueError("SECRET_KEY must be changed before startup")
        return value

    @model_validator(mode="after")
    def _guard_refresh_cookie(self) -> "Settings":
        if self.REFRESH_COOKIE_SAMESITE == "none" and not self.REFRESH_COOKIE_SECURE:
            raise ValueError("SameSite=None requires a Secure refresh cookie")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
