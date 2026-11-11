"""Concurrency and transaction safety tests."""

from __future__ import annotations

import pytest

from app.database.exceptions import VersionConflictError
from app.database.models.game import GameLifecycle, GameRecord
from app.database.session import Database
from app.repositories.game import GameRepository


@pytest.mark.asyncio
async def test_concurrent_optimistic_lock_updates(db: Database) -> None:
    # Seed a game
    async with db.session() as session:
        repo = GameRepository(session)
        await repo.create(
            GameRecord(
                game_id="race_game",
                status=GameLifecycle.ACTIVE,
                version=1,
                state={"counter": 0},
            )
        )

    # Worker 1 reads game (version 1)
    async with db.session() as session1:
        repo1 = GameRepository(session1)
        record1 = await repo1.get_by_game_id("race_game")
        assert record1 is not None
        v1 = record1.version

        # Worker 2 reads game (version 1)
        async with db.session() as session2:
            repo2 = GameRepository(session2)
            record2 = await repo2.get_by_game_id("race_game")
            assert record2 is not None
            v2 = record2.version

            # Worker 1 commits update from version 1 -> 2
            await repo1.save_snapshot("race_game", state={"counter": 1}, current_version=v1)

            # Worker 2 tries to commit with stale version 1 -> must fail
            with pytest.raises(VersionConflictError):
                await repo2.save_snapshot("race_game", state={"counter": 2}, current_version=v2)


@pytest.mark.asyncio
async def test_transaction_rollback_leaves_no_partial_data(db: Database) -> None:
    # Verify that an aborted session rolls back
    try:
        async with db.session() as session:
            repo = GameRepository(session)
            await repo.create(
                GameRecord(
                    game_id="rollback_test",
                    status=GameLifecycle.ACTIVE,
                    version=1,
                    state={},
                )
            )
            # Deliberately raise an exception to trigger session rollback
            raise RuntimeError("Forced abort")
    except RuntimeError:
        pass

    # Verify record was not persisted
    async with db.session() as session:
        repo = GameRepository(session)
        assert await repo.get_by_game_id("rollback_test") is None
