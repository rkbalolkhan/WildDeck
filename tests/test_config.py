import pytest
from pydantic import ValidationError

from app.config import Settings

TOKEN = "123456:TEST-token-value-not-real"


def make(**kwargs: object) -> Settings:
    return Settings(_env_file=None, **kwargs)  # type: ignore[arg-type]


def test_defaults() -> None:
    s = make(bot_token=TOKEN)
    assert s.bot_mode == "polling"
    assert s.log_level == "INFO"
    assert s.environment == "development"
    assert s.redis_url is None


def test_loads_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", TOKEN)
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("ENVIRONMENT", "production")
    s = make()
    assert s.log_level == "DEBUG"
    assert s.is_production


def test_missing_token_fails() -> None:
    with pytest.raises(ValidationError):
        make()


@pytest.mark.parametrize(
    "kwargs", [{"bot_mode": "carrier-pigeon"}, {"log_level": "LOUD"}, {"environment": "moon"}]
)
def test_invalid_values(kwargs: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        make(bot_token=TOKEN, **kwargs)


def test_webhook_requires_url_and_secret() -> None:
    with pytest.raises(ValidationError, match="BOT_WEBHOOK_URL"):
        make(bot_token=TOKEN, bot_mode="webhook")
    with pytest.raises(ValidationError, match="BOT_WEBHOOK_SECRET"):
        make(bot_token=TOKEN, bot_mode="webhook", bot_webhook_url="https://x.example/hook")
    with pytest.raises(ValidationError, match="https"):
        make(
            bot_token=TOKEN,
            bot_mode="webhook",
            bot_webhook_url="http://x.example/hook",
            bot_webhook_secret="s",
        )


def test_webhook_valid() -> None:
    s = make(
        bot_token=TOKEN,
        bot_mode="webhook",
        bot_webhook_url="https://x.example/hook",
        bot_webhook_secret="s3cret",
    )
    assert s.webhook_path == "/hook"


def test_empty_optional_values_are_none() -> None:
    s = make(bot_token=TOKEN, bot_webhook_url="", redis_url="")
    assert s.bot_webhook_url is None and s.redis_url is None
