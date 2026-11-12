"""Inline keyboards and CallbackData factories for WildDeck."""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


class MenuAction(CallbackData, prefix="menu"):
    """Callback data for global menu interactions."""

    action: str


class GameAction(CallbackData, prefix="game"):
    """Callback data for game-specific interactions."""

    action: str
    game_id: str


def start_keyboard(
    is_private: bool = True, bot_username: str | None = None
) -> InlineKeyboardMarkup:
    """Build the welcome /start inline keyboard."""
    builder = InlineKeyboardBuilder()

    if is_private:
        builder.button(text="📜 Rules", callback_data=MenuAction(action="rules").pack())
        builder.button(text="❓ Help", callback_data=MenuAction(action="help").pack())
        builder.button(text="ℹ️ About", callback_data=MenuAction(action="about").pack())
        builder.adjust(2, 1)

        if bot_username:
            builder.row(
                InlineKeyboardButton(
                    text="➕ Add to Group",
                    url=f"https://t.me/{bot_username}?startgroup=true",
                )
            )
    else:
        builder.button(text="📜 Rules", callback_data=MenuAction(action="rules").pack())
        builder.button(text="❓ Help", callback_data=MenuAction(action="help").pack())
        builder.adjust(2)

    return builder.as_markup()


def help_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard for /help message."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📜 Rules", callback_data=MenuAction(action="rules").pack())
    builder.button(text="ℹ️ About", callback_data=MenuAction(action="about").pack())
    builder.adjust(2)
    return builder.as_markup()


def rules_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard for /rules message."""
    builder = InlineKeyboardBuilder()
    builder.button(text="❓ Help", callback_data=MenuAction(action="help").pack())
    builder.button(text="ℹ️ About", callback_data=MenuAction(action="about").pack())
    builder.adjust(2)
    return builder.as_markup()


def about_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard for /about message."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📜 Rules", callback_data=MenuAction(action="rules").pack())
    builder.button(text="❓ Help", callback_data=MenuAction(action="help").pack())
    builder.adjust(2)
    return builder.as_markup()


def game_created_keyboard(game_id: str) -> InlineKeyboardMarkup:
    """Build keyboard shown when a new game lobby/session is created."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📊 Status",
        callback_data=GameAction(action="status", game_id=game_id).pack(),
    )
    builder.button(
        text="📜 Rules",
        callback_data=GameAction(action="rules", game_id=game_id).pack(),
    )
    builder.button(
        text="❌ Cancel Game",
        callback_data=GameAction(action="cancel", game_id=game_id).pack(),
    )
    builder.adjust(2, 1)
    return builder.as_markup()


def game_status_keyboard(game_id: str) -> InlineKeyboardMarkup:
    """Build keyboard shown on game status view."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🔄 Refresh",
        callback_data=GameAction(action="status", game_id=game_id).pack(),
    )
    builder.button(
        text="❌ Cancel Game",
        callback_data=GameAction(action="cancel", game_id=game_id).pack(),
    )
    builder.adjust(2)
    return builder.as_markup()


def game_conflict_keyboard(game_id: str) -> InlineKeyboardMarkup:
    """Build keyboard shown when attempting to create a game while one is active."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📊 View Active Game",
        callback_data=GameAction(action="status", game_id=game_id).pack(),
    )
    builder.button(
        text="❌ Cancel It",
        callback_data=GameAction(action="cancel", game_id=game_id).pack(),
    )
    builder.adjust(2)
    return builder.as_markup()
