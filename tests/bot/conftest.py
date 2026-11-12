"""Fixtures and mocks for Telegram bot integration tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram import Bot
from aiogram.types import Chat, Message, User
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import Database
from app.services.persistence import GamePersistenceService
from app.services.telegram_game import TelegramGameService

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def bot_test_engine() -> AsyncIterator[AsyncEngine]:
    """Isolated SQLite in-memory engine for bot tests."""
    engine = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest.fixture
async def bot_db(bot_test_engine: AsyncEngine) -> Database:
    """Database instance for bot tests."""
    database = Database.__new__(Database)
    database.engine = bot_test_engine
    database.session_factory = async_sessionmaker(bot_test_engine, expire_on_commit=False)
    return database


@pytest.fixture
def persistence_service(bot_db: Database) -> GamePersistenceService:
    return GamePersistenceService(bot_db)


@pytest.fixture
def telegram_game_service(
    bot_db: Database, persistence_service: GamePersistenceService
) -> TelegramGameService:
    return TelegramGameService(bot_db, persistence_service)


@pytest.fixture
def mock_bot() -> AsyncMock:
    bot = AsyncMock(spec=Bot)
    me = MagicMock(spec=User)
    me.username = "WildDeckBot"
    me.first_name = "WildDeck"
    me.is_bot = True
    bot.get_me.return_value = me

    # Default chat member status: regular member
    member = MagicMock()
    member.status = "member"
    bot.get_chat_member.return_value = member
    return bot


def make_user(
    user_id: int = 12345,
    first_name: str = "Alice",
    username: str | None = "alice",
) -> User:
    user = MagicMock(spec=User)
    user.id = user_id
    user.first_name = first_name
    user.last_name = None
    user.full_name = first_name
    user.username = username
    user.is_bot = False
    return user


def make_chat(chat_id: int = -1001234567890, chat_type: str = "group") -> Chat:
    chat = MagicMock(spec=Chat)
    chat.id = chat_id
    chat.type = chat_type
    chat.title = "UNO Test Group" if chat_type != "private" else None
    return chat


def make_message(
    text: str = "/start",
    chat_id: int = -1001234567890,
    chat_type: str = "group",
    user_id: int = 12345,
    user_name: str = "Alice",
    message_id: int = 999,
) -> Message:
    msg = AsyncMock(spec=Message)
    msg.text = text
    msg.message_id = message_id
    msg.chat = make_chat(chat_id, chat_type)
    msg.from_user = make_user(user_id, user_name)
    msg.message_thread_id = None
    msg.answer = AsyncMock()
    msg.reply = AsyncMock()
    return msg
