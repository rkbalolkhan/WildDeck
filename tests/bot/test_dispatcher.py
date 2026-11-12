"""Tests for dispatcher creation and configuration."""

from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

from app.bot.dispatcher import create_dispatcher, on_startup
from app.config import Settings
from app.database.session import Database
from app.services.persistence import GamePersistenceService
from app.services.telegram_game import TelegramGameService


def test_create_dispatcher_injects_services(bot_db: Database) -> None:
    settings = Settings(
        _env_file=None,
        bot_token=SecretStr("123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"),
    )

    dp = create_dispatcher(db=bot_db, settings=settings)

    assert dp["db"] is bot_db
    assert dp["settings"] is settings
    assert isinstance(dp["persistence"], GamePersistenceService)
    assert isinstance(dp["telegram_game"], TelegramGameService)


@pytest.mark.asyncio
async def test_on_startup_sets_commands(mock_bot: AsyncMock, bot_db: Database) -> None:
    # Healthcheck returns true
    bot_db.healthcheck = AsyncMock(return_value=True)

    await on_startup(mock_bot, bot_db)

    assert mock_bot.get_me.called
    assert mock_bot.set_my_commands.called
    args, _ = mock_bot.set_my_commands.call_args
    command_names = [cmd.command for cmd in args[0]]
    assert "start" in command_names
    assert "help" in command_names
    assert "rules" in command_names
    assert "newgame" in command_names
    assert "status" in command_names
    assert "cancel" in command_names
