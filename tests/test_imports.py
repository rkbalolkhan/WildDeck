import importlib

import pytest

MODULES = [
    "app.config",
    "app.main",
    "app.bot.dispatcher",
    "app.bot.handlers",
    "app.database",
    "app.database.models",
    "app.engine.game",
    "app.engine.card",
    "app.engine.deck",
    "app.engine.player",
    "app.engine.rules",
    "app.engine.actions",
    "app.themes.registry",
    "app.utils.logging",
    "app.services",
    "app.repositories",
    "app.scheduler",
]


@pytest.mark.parametrize("name", MODULES)
def test_import(name: str) -> None:
    importlib.import_module(name)


def test_dispatcher_builds_without_telegram() -> None:
    from app.bot.dispatcher import create_dispatcher
    from app.config import Settings
    from app.database import Database

    settings = Settings(_env_file=None, bot_token="123456:TEST-token-value-not-real")  # type: ignore[call-arg]
    db = Database(settings.database_url.get_secret_value())
    dp = create_dispatcher(db=db, settings=settings)
    assert dp.sub_routers
