"""Centralised, validated application configuration."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

_ASYNC_DRIVER = "postgresql+asyncpg"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    bot_token: SecretStr = Field(min_length=10)
    bot_mode: Literal["polling", "webhook"] = "polling"
    bot_webhook_url: str | None = None
    bot_webhook_secret: SecretStr | None = None
    bot_webhook_host: str = "127.0.0.1"
    bot_webhook_port: int = Field(default=8080, ge=1, le=65535)

    database_url: SecretStr = SecretStr("postgresql+asyncpg://uno:uno@localhost:5432/uno")
    redis_url: str | None = None

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    environment: Literal["development", "production", "testing"] = "development"

    @field_validator("bot_webhook_url", "bot_webhook_secret", "redis_url", mode="before")
    @classmethod
    def _empty_to_none(cls, value: object) -> object:
        # ".env.example" ships empty values; treat them as "not set".
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalise_database_url(cls, value: object) -> object:
        """Force the asyncpg driver so plain ``postgresql://`` URLs also work."""
        raw = value.get_secret_value() if isinstance(value, SecretStr) else value
        if not isinstance(raw, str):
            return value
        url = make_url(raw)
        if url.get_backend_name() != "postgresql":
            raise ValueError("DATABASE_URL must be a PostgreSQL URL")
        if url.drivername != _ASYNC_DRIVER:
            url = url.set(drivername=_ASYNC_DRIVER)
        return url.render_as_string(hide_password=False)

    @model_validator(mode="after")
    def _validate_webhook(self) -> Settings:
        if self.bot_mode == "webhook":
            if not self.bot_webhook_url:
                raise ValueError("BOT_WEBHOOK_URL is required when BOT_MODE=webhook")
            if urlparse(self.bot_webhook_url).scheme != "https":
                raise ValueError("BOT_WEBHOOK_URL must be an https:// URL")
            if self.bot_webhook_secret is None:
                raise ValueError("BOT_WEBHOOK_SECRET is required when BOT_MODE=webhook")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def webhook_path(self) -> str:
        return urlparse(self.bot_webhook_url or "").path or "/webhook"

    @property
    def safe_database_url(self) -> str:
        """Database URL with the password masked - safe for logs."""
        return make_url(self.database_url.get_secret_value()).render_as_string(hide_password=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
