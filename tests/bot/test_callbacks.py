"""Unit tests for inline callback queries."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import CallbackQuery, Message

from app.bot.handlers.callbacks import handle_game_callbacks, handle_menu_callbacks
from app.bot.keyboards import GameAction, MenuAction
from app.services.telegram_game import TelegramGameService
from tests.bot.conftest import make_chat, make_user


def make_callback_query(
    action_data: str,
    user_id: int = 123,
    user_name: str = "Alice",
    chat_id: int = -100999,
    chat_type: str = "group",
) -> CallbackQuery:
    cb = AsyncMock(spec=CallbackQuery)
    cb.data = action_data
    cb.from_user = make_user(user_id=user_id, first_name=user_name)

    msg = AsyncMock(spec=Message)
    msg.message_id = 42
    msg.chat = make_chat(chat_id=chat_id, chat_type=chat_type)
    msg.edit_text = AsyncMock()
    msg.answer = AsyncMock()
    cb.message = msg
    cb.answer = AsyncMock()
    return cb


@pytest.mark.asyncio
async def test_menu_callback_rules() -> None:
    action = MenuAction(action="rules")
    cb = make_callback_query(action.pack())

    await handle_menu_callbacks(cb, action)

    assert cb.answer.called
    assert cb.message.edit_text.called
    args, _ = cb.message.edit_text.call_args
    assert "Official UNO Rules" in args[0]


@pytest.mark.asyncio
async def test_menu_callback_help() -> None:
    action = MenuAction(action="help")
    cb = make_callback_query(action.pack())

    await handle_menu_callbacks(cb, action)

    assert cb.answer.called
    assert cb.message.edit_text.called
    args, _ = cb.message.edit_text.call_args
    assert "Command Guide" in args[0]


@pytest.mark.asyncio
async def test_menu_callback_about() -> None:
    action = MenuAction(action="about")
    cb = make_callback_query(action.pack())

    await handle_menu_callbacks(cb, action)

    assert cb.answer.called
    assert cb.message.edit_text.called
    args, _ = cb.message.edit_text.call_args
    assert "WildDeck UNO Bot" in args[0]


@pytest.mark.asyncio
async def test_game_callback_status_active(
    mock_bot: AsyncMock, telegram_game_service: TelegramGameService
) -> None:
    chat_id = -100555
    record, _ = await telegram_game_service.create_game(
        chat_id=chat_id, chat_type="group", user_id=1, user_name="Alice"
    )

    action = GameAction(action="status", game_id=record.game_id)
    cb = make_callback_query(action.pack(), chat_id=chat_id)

    await handle_game_callbacks(cb, action, mock_bot, telegram_game_service)

    assert cb.answer.called
    assert cb.message.edit_text.called
    args, _ = cb.message.edit_text.call_args
    assert record.game_id in args[0]


@pytest.mark.asyncio
async def test_game_callback_status_expired(
    mock_bot: AsyncMock, telegram_game_service: TelegramGameService
) -> None:
    action = GameAction(action="status", game_id="uno_nonexistent")
    cb = make_callback_query(action.pack())

    await handle_game_callbacks(cb, action, mock_bot, telegram_game_service)

    assert cb.answer.called
    _, kwargs = cb.answer.call_args
    assert kwargs.get("show_alert") is True


@pytest.mark.asyncio
async def test_game_callback_cancel_authorized(
    mock_bot: AsyncMock, telegram_game_service: TelegramGameService
) -> None:
    chat_id = -100666
    record, _ = await telegram_game_service.create_game(
        chat_id=chat_id, chat_type="group", user_id=10, user_name="Creator"
    )

    action = GameAction(action="cancel", game_id=record.game_id)
    cb = make_callback_query(action.pack(), user_id=10, chat_id=chat_id)

    await handle_game_callbacks(cb, action, mock_bot, telegram_game_service)

    assert cb.answer.called
    assert cb.message.edit_text.called
    args, _ = cb.message.edit_text.call_args
    assert "Game Cancelled" in args[0]


@pytest.mark.asyncio
async def test_game_callback_cancel_unauthorized(
    mock_bot: AsyncMock, telegram_game_service: TelegramGameService
) -> None:
    chat_id = -100777
    record, _ = await telegram_game_service.create_game(
        chat_id=chat_id, chat_type="group", user_id=10, user_name="Creator"
    )

    # Regular user attempting to cancel
    member = MagicMock()
    member.status = "member"
    mock_bot.get_chat_member.return_value = member

    action = GameAction(action="cancel", game_id=record.game_id)
    cb = make_callback_query(action.pack(), user_id=999, chat_id=chat_id)

    await handle_game_callbacks(cb, action, mock_bot, telegram_game_service)

    assert cb.answer.called
    _, kwargs = cb.answer.call_args
    assert kwargs.get("show_alert") is True
