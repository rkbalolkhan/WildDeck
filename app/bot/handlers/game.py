"""Handlers for game lifecycle commands: /newgame, /status, /cancel."""

from __future__ import annotations

import logging

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.context import TelegramContext
from app.bot.formatters import (
    format_error,
    format_game_already_exists,
    format_game_cancelled,
    format_game_created,
    format_game_status,
    format_no_active_game,
    format_unauthorized_cancel,
)
from app.bot.keyboards import (
    game_conflict_keyboard,
    game_created_keyboard,
    game_status_keyboard,
)
from app.services.telegram_game import (
    GameAlreadyExistsError,
    GameNotFoundError,
    TelegramGameService,
    UnauthorizedActionError,
)

logger = logging.getLogger(__name__)
router = Router(name="game")


async def is_chat_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Check if a user is an administrator or owner of a group chat."""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("creator", "administrator")
    except Exception as exc:
        logger.debug("Could not verify chat member admin status: %s", exc)
        return False


@router.message(Command("newgame"))
async def handle_newgame(message: Message, bot: Bot, telegram_game: TelegramGameService) -> None:
    """Handle /newgame command: initialize lobby or announce existing game conflict."""
    ctx = TelegramContext.from_message(message)

    try:
        record, game = await telegram_game.create_game(
            chat_id=ctx.chat_id,
            chat_type=ctx.chat_type,
            user_id=ctx.user_id,
            user_name=ctx.user_name,
            thread_id=ctx.thread_id,
        )
        text = format_game_created(record.game_id, ctx.user_name, ctx.chat_type)
        await message.answer(text, reply_markup=game_created_keyboard(record.game_id))
    except GameAlreadyExistsError as exc:
        existing_id = exc.game_id
        if not existing_id:
            existing = await telegram_game.get_active_game_for_chat(ctx.chat_id)
            existing_id = existing.game_id if existing else "unknown"

        existing_record = await telegram_game.get_game_by_id(existing_id)
        creator_name = (
            (existing_record.state.get("telegram") or {}).get("creator_name", "another player")
            if existing_record
            else "another player"
        )
        text = format_game_already_exists(existing_id, creator_name)
        await message.answer(text, reply_markup=game_conflict_keyboard(existing_id))
    except Exception as exc:
        logger.error("Failed to create game in chat %s: %s", ctx.chat_id, exc, exc_info=True)
        await message.answer(
            format_error("Unable to create a new game right now. Please try again.")
        )


@router.message(Command("cancel"))
async def handle_cancel(message: Message, bot: Bot, telegram_game: TelegramGameService) -> None:
    """Handle /cancel command: cancel active game if authorized."""
    ctx = TelegramContext.from_message(message)

    is_admin = False
    if ctx.is_group:
        is_admin = await is_chat_admin(bot, ctx.chat_id, ctx.user_id)

    try:
        record = await telegram_game.cancel_game(
            chat_id=ctx.chat_id,
            user_id=ctx.user_id,
            is_admin=is_admin,
        )
        text = format_game_cancelled(record.game_id, ctx.user_name)
        await message.answer(text)
    except GameNotFoundError:
        await message.answer(format_no_active_game())
    except UnauthorizedActionError:
        await message.answer(format_unauthorized_cancel())
    except Exception as exc:
        logger.error("Failed to cancel game in chat %s: %s", ctx.chat_id, exc, exc_info=True)
        await message.answer(format_error("Failed to cancel game. Please try again."))


@router.message(Command("status"))
async def handle_status(message: Message, telegram_game: TelegramGameService) -> None:
    """Handle /status command: show detailed summary of active game."""
    ctx = TelegramContext.from_message(message)

    try:
        record, game = await telegram_game.get_game_status(ctx.chat_id)
    except GameNotFoundError:
        await message.answer(format_no_active_game())
        return

    meta = record.state.get("telegram") or {}
    creator_name = meta.get("creator_name", "Unknown")
    players_data = record.state.get("players", [])
    player_names = [p.get("name", f"Player {p.get('user_id')}") for p in players_data]

    top_card_str: str | None = None
    draw_pile_count: int | None = None
    current_player_name: str | None = None

    if game is not None:
        draw_pile_count = len(game.deck.draw_pile)
        if game.deck.discard_pile:
            top_card_str = str(game.deck.top_discard)
        if game.players and 0 <= game.current_index < len(game.players):
            current_player_name = game.players[game.current_index].name

    text = format_game_status(
        game_id=record.game_id,
        status=record.status.value,
        creator_name=creator_name,
        player_names=player_names,
        current_player=current_player_name,
        top_card=top_card_str,
        draw_pile_count=draw_pile_count,
    )
    await message.answer(text, reply_markup=game_status_keyboard(record.game_id))
