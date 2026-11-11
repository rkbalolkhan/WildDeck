import pytest

ENV_KEYS = (
    "BOT_TOKEN",
    "BOT_MODE",
    "BOT_WEBHOOK_URL",
    "BOT_WEBHOOK_SECRET",
    "BOT_WEBHOOK_HOST",
    "BOT_WEBHOOK_PORT",
    "DATABASE_URL",
    "REDIS_URL",
    "LOG_LEVEL",
    "ENVIRONMENT",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests never see the developer's real environment."""
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
