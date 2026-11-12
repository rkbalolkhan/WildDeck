"""Bot and dispatcher construction, router registration and lifecycle hooks."""

from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from app.bot.handlers import ROUTERS
from app.config import Settings
from app.database import Database
from app.services.persistence import GamePersistenceService
from app.services.telegram_game import TelegramGameService

logger = logging.getLogger(__name__)

DEFAULT_BOT_COMMANDS = [
    BotCommand(command="start", description="Start WildDeck and open main menu"),
    BotCommand(command="help", description="Show bot command guide"),
    BotCommand(command="rules", description="View official UNO rules"),
    BotCommand(command="about", description="About WildDeck"),
    BotCommand(command="newgame", description="Create a new UNO game lobby"),
    BotCommand(command="status", description="Check current game status"),
    BotCommand(command="cancel", description="Cancel the current game"),
]


def create_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def register_routers(dp: Dispatcher, routers: tuple[Router, ...] = ROUTERS) -> None:
    for router in routers:
        router._parent_router = None
        dp.include_router(router)


async def on_startup(bot: Bot, db: Database) -> None:
    if not await db.healthcheck():
        raise RuntimeError("Database is unreachable; aborting startup")
    try:
        me = await bot.get_me()
        logger.info("Bot started as @%s", me.username)
        await bot.set_my_commands(DEFAULT_BOT_COMMANDS)
    except Exception as exc:
        logger.warning("Could not set bot commands on startup: %s", exc)


async def on_shutdown() -> None:
    logger.info("Bot shutting down")


def create_dispatcher(
    *,
    db: Database,
    settings: Settings,
    persistence: GamePersistenceService | None = None,
    telegram_game: TelegramGameService | None = None,
) -> Dispatcher:
    """Build the dispatcher. Dependencies are injected via workflow data."""
    game_persistence = persistence or GamePersistenceService(db)
    game_service = telegram_game or TelegramGameService(db, game_persistence)

    dp = Dispatcher(
        db=db,
        settings=settings,
        persistence=game_persistence,
        telegram_game=game_service,
    )
    register_routers(dp)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    return dp
