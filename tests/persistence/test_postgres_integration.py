"""PostgreSQL-specific integration tests verifying native DB capabilities."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.exceptions import VersionConflictError
from app.database.models.game import GameLifecycle, GameRecord
from app.database.session import Database
from app.repositories.game import GameRepository

POSTGRES_TEST_URL = os.getenv("TEST_DATABASE_URL", "")
requires_postgres = pytest.mark.skipif(
    not POSTGRES_TEST_URL or "postgres" not in POSTGRES_TEST_URL,
    reason="Requires PostgreSQL test database configured via TEST_DATABASE_URL",
)


@requires_postgres
@pytest.mark.asyncio
async def test_postgres_jsonb_type_and_query(session: AsyncSession) -> None:
    """Verify PostgreSQL-specific JSONB storage and native operators."""
    repo = GameRepository(session)
    record = GameRecord(
        game_id="pg_jsonb_test",
        status=GameLifecycle.ACTIVE,
        version=1,
        state={
            "players": [{"user_id": 1, "name": "Alice"}],
            "config": {"rules": {"auto_uno": True}},
        },
    )
    await repo.create(record)

    stmt = text(
        "SELECT state->'config'->'rules'->>'auto_uno' FROM games WHERE game_id = 'pg_jsonb_test'"
    )
    result = await session.execute(stmt)
    val = result.scalar_one()
    assert val == "true"


@requires_postgres
@pytest.mark.asyncio
async def test_postgres_concurrent_updates(db: Database) -> None:
    """Verify optimistic concurrency control against real PostgreSQL."""
    async with db.session() as session:
        repo = GameRepository(session)
        await repo.create(
            GameRecord(
                game_id="pg_race_test",
                status=GameLifecycle.ACTIVE,
                version=1,
                state={"turn": 0},
            )
        )

    # Session 1 reads version 1
    async with db.session() as s1:
        repo1 = GameRepository(s1)
        r1 = await repo1.get_by_game_id("pg_race_test")
        assert r1 is not None

        # Session 2 reads version 1
        async with db.session() as s2:
            repo2 = GameRepository(s2)
            r2 = await repo2.get_by_game_id("pg_race_test")
            assert r2 is not None

            # S1 updates 1 -> 2
            await repo1.save_snapshot("pg_race_test", state={"turn": 1}, current_version=1)

            # S2 tries updating with stale version 1 -> VersionConflictError
            with pytest.raises(VersionConflictError):
                await repo2.save_snapshot("pg_race_test", state={"turn": 2}, current_version=1)
