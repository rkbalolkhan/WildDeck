"""Handlers for basic informational commands: /start, /help, /rules, /about."""

from __future__ import annotations

import logging

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.context import TelegramContext
from app.bot.formatters import (
    format_about_message,
    format_help_message,
    format_rules_message,
    format_start_message,
)
from app.bot.keyboards import (
    about_keyboard,
    help_keyboard,
    rules_keyboard,
    start_keyboard,
)

logger = logging.getLogger(__name__)
router = Router(name="start")


@router.message(Command("start"))
async def handle_start(message: Message, bot: Bot) -> None:
    """Handle /start command with dynamic greeting and quick action buttons."""
    ctx = TelegramContext.from_message(message)
    bot_username: str | None = None
    try:
        me = await bot.get_me()
        bot_username = me.username
    except Exception:
        pass

    text = format_start_message(ctx.user_name, is_private=ctx.is_private)
    keyboard = start_keyboard(is_private=ctx.is_private, bot_username=bot_username)
    await message.answer(text, reply_markup=keyboard)


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    """Handle /help command with complete usage instructions."""
    text = format_help_message()
    await message.answer(text, reply_markup=help_keyboard())


@router.message(Command("rules"))
async def handle_rules(message: Message) -> None:
    """Handle /rules command with official UNO card gameplay rules."""
    text = format_rules_message()
    await message.answer(text, reply_markup=rules_keyboard())


@router.message(Command("about"))
async def handle_about(message: Message) -> None:
    """Handle /about command describing WildDeck and current release status."""
    text = format_about_message()
    await message.answer(text, reply_markup=about_keyboard())
