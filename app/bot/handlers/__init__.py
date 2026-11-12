"""Handler routers. Feature routers are added to ``ROUTERS`` as phases land."""

from aiogram import Router

from app.bot.handlers import callbacks, errors, game, start

ROUTERS: tuple[Router, ...] = (
    errors.router,
    start.router,
    game.router,
    callbacks.router,
)
