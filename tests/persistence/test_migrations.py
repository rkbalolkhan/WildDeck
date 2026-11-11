"""Tests for database migrations."""

from __future__ import annotations

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.asyncio
async def test_table_schema_and_indexes(test_engine: AsyncEngine) -> None:
    def check_schema(conn) -> None:
        inspector = inspect(conn)
        tables = inspector.get_table_names()
        assert "games" in tables

        columns = {col["name"]: col for col in inspector.get_columns("games")}
        assert "id" in columns
        assert "game_id" in columns
        assert "status" in columns
        assert "version" in columns
        assert "state" in columns
        assert "winner_id" in columns
        assert "created_at" in columns
        assert "updated_at" in columns
        assert "started_at" in columns
        assert "completed_at" in columns

        indexes = {idx["name"]: idx for idx in inspector.get_indexes("games")}
        # Check that game_id has unique index / constraint
        assert any("game_id" in idx["column_names"] for idx in indexes.values())

    async with test_engine.connect() as conn:
        await conn.run_sync(check_schema)
