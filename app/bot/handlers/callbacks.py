"""Handlers for inline keyboard callback queries."""

from __future__ import annotations

import logging

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery

from app.bot.context import TelegramContext
from app.bot.formatters import (
    format_about_message,
    format_game_cancelled,
    format_game_status,
    format_help_message,
    format_rules_message,
)
from app.bot.handlers.game import is_chat_admin
from app.bot.keyboards import (
    GameAction,
    MenuAction,
    about_keyboard,
    game_status_keyboard,
    help_keyboard,
    rules_keyboard,
)
from app.database.models.game import GameLifecycle
from app.services.telegram_game import (
    GameNotFoundError,
    TelegramGameService,
    UnauthorizedActionError,
)

logger = logging.getLogger(__name__)
router = Router(name="callbacks")


@router.callback_query(MenuAction.filter())
async def handle_menu_callbacks(callback: CallbackQuery, callback_data: MenuAction) -> None:
    """Handle navigation menu clicks."""
    action = callback_data.action

    if action == "rules":
        text = format_rules_message()
        kb = rules_keyboard()
    elif action == "help":
        text = format_help_message()
        kb = help_keyboard()
    elif action == "about":
        text = format_about_message()
        kb = about_keyboard()
    else:
        await callback.answer("Unknown action", show_alert=False)
        return

    try:
        if callback.message:
            await callback.message.edit_text(text, reply_markup=kb)
        else:
            await callback.answer()
            return
    except TelegramAPIError as exc:
        logger.debug("Failed to edit menu message: %s", exc)

    await callback.answer()


@router.callback_query(GameAction.filter())
async def handle_game_callbacks(
    callback: CallbackQuery,
    callback_data: GameAction,
    bot: Bot,
    telegram_game: TelegramGameService,
) -> None:
    """Handle game-specific callbacks: status, rules, and cancel."""
    action = callback_data.action
    game_id = callback_data.game_id
    ctx = TelegramContext.from_callback(callback)

    if action == "rules":
        await callback.answer()
        if callback.message:
            await callback.message.answer(format_rules_message(), reply_markup=rules_keyboard())
        return

    if action == "status":
        record = await telegram_game.get_game_by_id(game_id)
        if record is None or record.status in (
            GameLifecycle.COMPLETED,
            GameLifecycle.CANCELLED,
        ):
            await callback.answer(
                "This game is no longer active or does not exist.", show_alert=True
            )
            return

        meta = record.state.get("telegram") or {}
        creator_name = meta.get("creator_name", "Unknown")
        players_data = record.state.get("players", [])
        player_names = [p.get("name", f"Player {p.get('user_id')}") for p in players_data]

        text = format_game_status(
            game_id=record.game_id,
            status=record.status.value,
            creator_name=creator_name,
            player_names=player_names,
        )

        try:
            if callback.message:
                await callback.message.edit_text(
                    text, reply_markup=game_status_keyboard(record.game_id)
                )
            await callback.answer("Status refreshed!")
        except TelegramAPIError:
            await callback.answer("Status is already up to date.")
        return

    if action == "cancel":
        record = await telegram_game.get_game_by_id(game_id)
        if record is None or record.status in (
            GameLifecycle.COMPLETED,
            GameLifecycle.CANCELLED,
        ):
            await callback.answer("This game is already ended or cancelled.", show_alert=True)
            return

        is_admin = False
        if ctx.is_group:
            is_admin = await is_chat_admin(bot, ctx.chat_id, ctx.user_id)

        try:
            cancelled_record = await telegram_game.cancel_game(
                chat_id=ctx.chat_id,
                user_id=ctx.user_id,
                is_admin=is_admin,
            )
            await callback.answer("Game cancelled successfully.")
            if callback.message:
                await callback.message.edit_text(
                    format_game_cancelled(cancelled_record.game_id, ctx.user_name)
                )
        except UnauthorizedActionError:
            await callback.answer(
                "Permission denied: Only the game creator or chat admins can cancel.",
                show_alert=True,
            )
        except GameNotFoundError:
            await callback.answer("No active game to cancel.", show_alert=True)
        except Exception as exc:
            logger.error("Failed to cancel game via callback %s: %s", game_id, exc)
            await callback.answer("Error cancelling game. Please try again.", show_alert=True)
        return

    await callback.answer("Unhandled game action.")
