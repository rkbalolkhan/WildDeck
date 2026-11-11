"""Application entry point: ``python -m app.main``."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from app.bot.dispatcher import create_bot, create_dispatcher
from app.config import Settings
from app.database import Database
from app.utils.logging import setup_logging

logger = logging.getLogger(__name__)


async def _run_webhook(bot: Bot, dp: Dispatcher, settings: Settings) -> None:
    assert settings.bot_webhook_url and settings.bot_webhook_secret  # validated in Settings
    secret = settings.bot_webhook_secret.get_secret_value()

    async def healthz(_: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    app = web.Application()
    app.router.add_get("/healthz", healthz)
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=secret).register(
        app, path=settings.webhook_path
    )
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()  # triggers dispatcher startup hooks
    try:
        await web.TCPSite(runner, settings.bot_webhook_host, settings.bot_webhook_port).start()
        await bot.set_webhook(settings.bot_webhook_url, secret_token=secret)
        logger.info(
            "Webhook server listening on %s:%s",
            settings.bot_webhook_host,
            settings.bot_webhook_port,
        )

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError):  # e.g. Windows
                loop.add_signal_handler(sig, stop.set)
        await stop.wait()
    finally:
        with contextlib.suppress(Exception):
            await bot.delete_webhook()
        await runner.cleanup()  # triggers dispatcher shutdown hooks


async def run(settings: Settings) -> None:
    db = Database(settings.database_url.get_secret_value(), echo=settings.log_level == "DEBUG")
    bot = create_bot(settings)
    dp = create_dispatcher(db=db, settings=settings)
    try:
        if settings.bot_mode == "polling":
            logger.info("Starting in polling mode (%s)", settings.environment)
            await bot.delete_webhook()
            await dp.start_polling(bot)  # handles SIGINT/SIGTERM itself
        else:
            logger.info("Starting in webhook mode (%s)", settings.environment)
            await _run_webhook(bot, dp, settings)
    finally:
        await bot.session.close()
        await db.dispose()
        logger.info("Shutdown complete")


def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    setup_logging(
        settings.log_level,
        secrets=[
            settings.bot_token.get_secret_value(),
            settings.bot_webhook_secret.get_secret_value() if settings.bot_webhook_secret else "",
        ],
    )
    logger.info("Database: %s", settings.safe_database_url)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run(settings))


if __name__ == "__main__":
    main()
