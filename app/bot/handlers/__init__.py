"""Handler routers. Feature routers are added to ``ROUTERS`` as phases land."""

from aiogram import Router

from app.bot.handlers import errors

ROUTERS: tuple[Router, ...] = (errors.router,)
