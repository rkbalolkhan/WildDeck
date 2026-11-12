"""Fixtures for database persistence tests."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import Database

TEST_DB_URL = os.getenv("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")


@pytest.fixture
async def test_engine() -> AsyncIterator[AsyncEngine]:
    """Create an isolated test engine."""
    if "sqlite" in TEST_DB_URL:
        engine = create_async_engine(
            TEST_DB_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        dev_url = os.getenv("DATABASE_URL", "")
        if dev_url and TEST_DB_URL == dev_url:
            raise ValueError(
                "TEST_DATABASE_URL must point to a dedicated test database, "
                "not the development database."
            )

        engine = create_async_engine(TEST_DB_URL, pool_pre_ping=True)
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception as exc:
            await engine.dispose()
            pytest.skip(f"PostgreSQL test database unavailable ({TEST_DB_URL}): {exc}")

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
async def db(test_engine: AsyncEngine) -> Database:
    """Database instance wrapping the test engine."""
    database = Database.__new__(Database)
    database.engine = test_engine
    database.session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    return database


@pytest.fixture
async def session(db: Database) -> AsyncIterator[AsyncSession]:
    """Yield an individual test session rolled back after use."""
    async with db.session_factory() as sess:
        yield sess
        await sess.rollback()
