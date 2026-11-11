"""Bot and dispatcher construction, router registration and lifecycle hooks."""

from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.bot.handlers import ROUTERS
from app.config import Settings
from app.database import Database

logger = logging.getLogger(__name__)


def create_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def register_routers(dp: Dispatcher, routers: tuple[Router, ...] = ROUTERS) -> None:
    for router in routers:
        dp.include_router(router)


async def on_startup(bot: Bot, db: Database) -> None:
    if not await db.healthcheck():
        raise RuntimeError("Database is unreachable; aborting startup")
    me = await bot.get_me()
    logger.info("Bot started as @%s", me.username)


async def on_shutdown() -> None:
    logger.info("Bot shutting down")


def create_dispatcher(*, db: Database, settings: Settings) -> Dispatcher:
    """Build the dispatcher. Dependencies are injected via workflow data."""
    dp = Dispatcher(db=db, settings=settings)
    register_routers(dp)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    return dp
