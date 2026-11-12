"""Integration and unit tests for command handlers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.bot.handlers.game import handle_cancel, handle_newgame, handle_status
from app.bot.handlers.start import handle_about, handle_help, handle_rules, handle_start
from app.services.telegram_game import TelegramGameService
from tests.bot.conftest import make_message


@pytest.mark.asyncio
async def test_handle_start_private(mock_bot: AsyncMock) -> None:
    msg = make_message(text="/start", chat_type="private", user_name="Alice")
    await handle_start(msg, mock_bot)

    assert msg.answer.called
    args, kwargs = msg.answer.call_args
    assert "Alice" in args[0]
    assert "Welcome to WildDeck" in args[0]
    assert kwargs.get("reply_markup") is not None


@pytest.mark.asyncio
async def test_handle_start_group(mock_bot: AsyncMock) -> None:
    msg = make_message(text="/start", chat_type="group", user_name="Bob")
    await handle_start(msg, mock_bot)

    assert msg.answer.called
    args, _ = msg.answer.call_args
    assert "Bob" in args[0]
    assert "ready in this group" in args[0]


@pytest.mark.asyncio
async def test_handle_help() -> None:
    msg = make_message(text="/help")
    await handle_help(msg)

    assert msg.answer.called
    args, _ = msg.answer.call_args
    assert "Command Guide" in args[0]


@pytest.mark.asyncio
async def test_handle_rules() -> None:
    msg = make_message(text="/rules")
    await handle_rules(msg)

    assert msg.answer.called
    args, _ = msg.answer.call_args
    assert "Official UNO Rules" in args[0]


@pytest.mark.asyncio
async def test_handle_about() -> None:
    msg = make_message(text="/about")
    await handle_about(msg)

    assert msg.answer.called
    args, _ = msg.answer.call_args
    assert "WildDeck UNO Bot" in args[0]


@pytest.mark.asyncio
async def test_handle_newgame_success(
    mock_bot: AsyncMock, telegram_game_service: TelegramGameService
) -> None:
    msg = make_message(
        text="/newgame",
        chat_id=-100111,
        chat_type="group",
        user_id=1,
        user_name="Alice",
    )
    await handle_newgame(msg, mock_bot, telegram_game_service)

    assert msg.answer.called
    args, kwargs = msg.answer.call_args
    assert "New UNO Game Created" in args[0]
    assert "Alice" in args[0]
    assert kwargs.get("reply_markup") is not None


@pytest.mark.asyncio
async def test_handle_newgame_already_exists(
    mock_bot: AsyncMock, telegram_game_service: TelegramGameService
) -> None:
    chat_id = -100222
    # Create first game
    msg1 = make_message(text="/newgame", chat_id=chat_id, user_id=1, user_name="Alice")
    await handle_newgame(msg1, mock_bot, telegram_game_service)

    # Attempt second game in same chat
    msg2 = make_message(text="/newgame", chat_id=chat_id, user_id=2, user_name="Bob")
    await handle_newgame(msg2, mock_bot, telegram_game_service)

    assert msg2.answer.called
    args, kwargs = msg2.answer.call_args
    assert "already in progress" in args[0]
    assert kwargs.get("reply_markup") is not None


@pytest.mark.asyncio
async def test_handle_cancel_by_creator(
    mock_bot: AsyncMock, telegram_game_service: TelegramGameService
) -> None:
    chat_id = -100333
    await telegram_game_service.create_game(
        chat_id=chat_id, chat_type="group", user_id=10, user_name="Creator"
    )

    cancel_msg = make_message(text="/cancel", chat_id=chat_id, user_id=10, user_name="Creator")
    await handle_cancel(cancel_msg, mock_bot, telegram_game_service)

    assert cancel_msg.answer.called
    args, _ = cancel_msg.answer.call_args
    assert "Game Cancelled" in args[0]


@pytest.mark.asyncio
async def test_handle_cancel_by_admin(
    mock_bot: AsyncMock, telegram_game_service: TelegramGameService
) -> None:
    chat_id = -100444
    await telegram_game_service.create_game(
        chat_id=chat_id, chat_type="group", user_id=10, user_name="Creator"
    )

    # Set mock_bot chat member status to administrator
    admin_member = MagicMock()
    admin_member.status = "administrator"
    mock_bot.get_chat_member.return_value = admin_member

    cancel_msg = make_message(text="/cancel", chat_id=chat_id, user_id=999, user_name="Admin")
    await handle_cancel(cancel_msg, mock_bot, telegram_game_service)

    assert cancel_msg.answer.called
    args, _ = cancel_msg.answer.call_args
    assert "Game Cancelled" in args[0]


@pytest.mark.asyncio
async def test_handle_cancel_unauthorized(
    mock_bot: AsyncMock, telegram_game_service: TelegramGameService
) -> None:
    chat_id = -100555
    await telegram_game_service.create_game(
        chat_id=chat_id, chat_type="group", user_id=10, user_name="Creator"
    )

    # Regular member trying to cancel
    member = MagicMock()
    member.status = "member"
    mock_bot.get_chat_member.return_value = member

    cancel_msg = make_message(text="/cancel", chat_id=chat_id, user_id=777, user_name="Intruder")
    await handle_cancel(cancel_msg, mock_bot, telegram_game_service)

    assert cancel_msg.answer.called
    args, _ = cancel_msg.answer.call_args
    assert "Permission Denied" in args[0]


@pytest.mark.asyncio
async def test_handle_status_no_game(telegram_game_service: TelegramGameService) -> None:
    msg = make_message(text="/status", chat_id=-100666)
    await handle_status(msg, telegram_game_service)

    assert msg.answer.called
    args, _ = msg.answer.call_args
    assert "No active game" in args[0]


@pytest.mark.asyncio
async def test_handle_status_active_game(
    mock_bot: AsyncMock, telegram_game_service: TelegramGameService
) -> None:
    chat_id = -100777
    record, _ = await telegram_game_service.create_game(
        chat_id=chat_id, chat_type="group", user_id=1, user_name="Alice"
    )

    msg = make_message(text="/status", chat_id=chat_id)
    await handle_status(msg, telegram_game_service)

    assert msg.answer.called
    args, kwargs = msg.answer.call_args
    assert record.game_id in args[0]
    assert "Alice" in args[0]
    assert kwargs.get("reply_markup") is not None
