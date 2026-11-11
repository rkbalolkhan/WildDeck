from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.database import Base, Database

TOKEN = "123456:TEST-token-value-not-real"


def make(**kwargs: object) -> Settings:
    return Settings(_env_file=None, bot_token=TOKEN, **kwargs)  # type: ignore[arg-type]


def test_plain_postgres_url_gets_asyncpg_driver() -> None:
    s = make(database_url="postgresql://u:p@db:5432/uno")
    assert s.database_url.get_secret_value().startswith("postgresql+asyncpg://")


def test_non_postgres_url_rejected() -> None:
    with pytest.raises(ValueError, match="PostgreSQL"):
        make(database_url="sqlite:///x.db")


def test_safe_url_hides_password() -> None:
    s = make(database_url="postgresql+asyncpg://u:hunter2@db:5432/uno")
    assert "hunter2" not in s.safe_database_url
    assert "hunter2" not in repr(s)


async def test_healthcheck_false_when_unreachable() -> None:
    db = Database("postgresql+asyncpg://u:p@127.0.0.1:1/none")
    try:
        assert await db.healthcheck() is False
    finally:
        await db.dispose()


async def test_healthcheck_true_with_mocked_connection() -> None:
    db = Database("postgresql+asyncpg://u:p@127.0.0.1:1/none")
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
    ctx.__aexit__ = AsyncMock(return_value=False)
    with patch.object(type(db.engine), "connect", return_value=ctx):
        assert await db.healthcheck() is True
    await db.dispose()


def test_base_metadata_contains_phase_04_models() -> None:
    import app.database.models  # noqa: F401

    assert "games" in Base.metadata.tables
