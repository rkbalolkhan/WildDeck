"""Unit tests for TelegramContext extraction and sanitization."""

from unittest.mock import MagicMock

from aiogram.types import CallbackQuery, Chat, Message, User

from app.bot.context import TelegramContext


def test_telegram_context_from_message_private() -> None:
    user = MagicMock(spec=User)
    user.id = 42
    user.first_name = "Alice"
    user.full_name = "Alice Wonder"
    user.username = "alicew"

    chat = MagicMock(spec=Chat)
    chat.id = 42
    chat.type = "private"

    msg = MagicMock(spec=Message)
    msg.from_user = user
    msg.chat = chat
    msg.message_thread_id = None
    msg.message_id = 101

    ctx = TelegramContext.from_message(msg)

    assert ctx.user_id == 42
    assert ctx.user_name == "Alice Wonder"
    assert ctx.username == "alicew"
    assert ctx.chat_id == 42
    assert ctx.chat_type == "private"
    assert ctx.is_private is True
    assert ctx.is_group is False
    assert ctx.message_id == 101


def test_telegram_context_from_message_group() -> None:
    user = MagicMock(spec=User)
    user.id = 123
    user.first_name = "Bob"
    user.full_name = "Bob"
    user.username = None

    chat = MagicMock(spec=Chat)
    chat.id = -100999
    chat.type = "supergroup"

    msg = MagicMock(spec=Message)
    msg.from_user = user
    msg.chat = chat
    msg.message_thread_id = 55
    msg.message_id = 202

    ctx = TelegramContext.from_message(msg)

    assert ctx.user_id == 123
    assert ctx.user_name == "Bob"
    assert ctx.username is None
    assert ctx.chat_id == -100999
    assert ctx.chat_type == "supergroup"
    assert ctx.is_private is False
    assert ctx.is_group is True
    assert ctx.thread_id == 55


def test_telegram_context_sanitization() -> None:
    user = MagicMock(spec=User)
    user.id = 777
    user.first_name = "<script>alert('xss')</script>"
    user.full_name = "<script>alert('xss')</script>"
    user.username = "hacker"

    chat = MagicMock(spec=Chat)
    chat.id = 1
    chat.type = "private"

    msg = MagicMock(spec=Message)
    msg.from_user = user
    msg.chat = chat
    msg.message_thread_id = None
    msg.message_id = 1

    ctx = TelegramContext.from_message(msg)
    assert "<script>" not in ctx.user_name
    assert "&lt;script&gt;" in ctx.user_name


def test_telegram_context_from_callback() -> None:
    user = MagicMock(spec=User)
    user.id = 99
    user.first_name = "Charlie"
    user.full_name = "Charlie Brown"
    user.username = "cbrown"

    chat = MagicMock(spec=Chat)
    chat.id = -500
    chat.type = "group"

    msg = MagicMock(spec=Message)
    msg.chat = chat
    msg.message_thread_id = None
    msg.message_id = 303

    cb = MagicMock(spec=CallbackQuery)
    cb.from_user = user
    cb.message = msg

    ctx = TelegramContext.from_callback(cb)
    assert ctx.user_id == 99
    assert ctx.user_name == "Charlie Brown"
    assert ctx.chat_id == -500
    assert ctx.chat_type == "group"
    assert ctx.is_group is True
