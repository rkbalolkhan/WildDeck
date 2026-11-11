"""Unit and integration tests for GameRepository."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.exceptions import (
    GameAlreadyExistsError,
    GameNotFoundError,
    InvalidLifecycleTransitionError,
    VersionConflictError,
)
from app.database.models.game import GameLifecycle, GameRecord
from app.repositories.game import GameRepository


@pytest.mark.asyncio
async def test_create_and_retrieve_game(session: AsyncSession) -> None:
    repo = GameRepository(session)
    record = GameRecord(
        game_id="game_test_01",
        status=GameLifecycle.CREATED,
        version=1,
        state={"dummy": "state"},
    )
    created = await repo.create(record)
    assert created.id is not None
    assert created.game_id == "game_test_01"
    assert created.version == 1
    assert created.status == GameLifecycle.CREATED

    fetched_by_id = await repo.get_by_id(created.id)
    assert fetched_by_id is not None
    assert fetched_by_id.game_id == "game_test_01"

    fetched_by_gid = await repo.get_by_game_id("game_test_01")
    assert fetched_by_gid is not None
    assert fetched_by_gid.id == created.id


@pytest.mark.asyncio
async def test_duplicate_game_id_raises_error(session: AsyncSession) -> None:
    repo = GameRepository(session)
    record1 = GameRecord(
        game_id="dup_test",
        status=GameLifecycle.CREATED,
        version=1,
        state={"v": 1},
    )
    await repo.create(record1)

    record2 = GameRecord(
        game_id="dup_test",
        status=GameLifecycle.CREATED,
        version=1,
        state={"v": 2},
    )
    with pytest.raises(GameAlreadyExistsError):
        await repo.create(record2)


@pytest.mark.asyncio
async def test_get_by_status_and_active_games(session: AsyncSession) -> None:
    repo = GameRepository(session)
    await repo.create(GameRecord(game_id="g1", status=GameLifecycle.CREATED, version=1, state={}))
    await repo.create(GameRecord(game_id="g2", status=GameLifecycle.ACTIVE, version=1, state={}))
    await repo.create(GameRecord(game_id="g3", status=GameLifecycle.ACTIVE, version=1, state={}))
    await repo.create(GameRecord(game_id="g4", status=GameLifecycle.COMPLETED, version=1, state={}))

    active_games = await repo.get_active_games()
    assert len(active_games) == 2
    assert {g.game_id for g in active_games} == {"g2", "g3"}

    created_games = await repo.get_by_status(GameLifecycle.CREATED)
    assert len(created_games) == 1
    assert created_games[0].game_id == "g1"

    multi_status = await repo.get_by_status([GameLifecycle.CREATED, GameLifecycle.COMPLETED])
    assert len(multi_status) == 2


@pytest.mark.asyncio
async def test_save_snapshot_success_and_concurrency(session: AsyncSession) -> None:
    repo = GameRepository(session)
    await repo.create(
        GameRecord(game_id="snap_1", status=GameLifecycle.ACTIVE, version=1, state={"step": 0})
    )

    # Successful update from version 1 -> 2
    updated = await repo.save_snapshot(
        "snap_1",
        state={"step": 1},
        current_version=1,
    )
    assert updated.version == 2
    assert updated.state == {"step": 1}

    # Stale update from version 1 must fail
    with pytest.raises(VersionConflictError):
        await repo.save_snapshot(
            "snap_1",
            state={"step": "stale"},
            current_version=1,
        )

    # Missing game update must fail
    with pytest.raises(GameNotFoundError):
        await repo.save_snapshot(
            "non_existent",
            state={"step": 99},
            current_version=1,
        )


@pytest.mark.asyncio
async def test_lifecycle_transitions(session: AsyncSession) -> None:
    repo = GameRepository(session)
    await repo.create(
        GameRecord(game_id="life_1", status=GameLifecycle.CREATED, version=1, state={})
    )

    started = await repo.mark_started("life_1", current_version=1)
    assert started.status == GameLifecycle.ACTIVE
    assert started.version == 2
    assert started.started_at is not None

    completed = await repo.mark_completed("life_1", current_version=2, winner_id=101)
    assert completed.status == GameLifecycle.COMPLETED
    assert completed.version == 3
    assert completed.winner_id == 101
    assert completed.completed_at is not None

    # Cannot transition completed game back to active
    with pytest.raises(InvalidLifecycleTransitionError):
        await repo.mark_started("life_1", current_version=3)

    # Cannot update state on completed game
    with pytest.raises(InvalidLifecycleTransitionError):
        await repo.save_snapshot("life_1", state={"step": 2}, current_version=3)


@pytest.mark.asyncio
async def test_delete_game(session: AsyncSession) -> None:
    repo = GameRepository(session)
    await repo.create(
        GameRecord(game_id="del_me", status=GameLifecycle.CREATED, version=1, state={})
    )
    assert await repo.delete("del_me") is True
    assert await repo.get_by_game_id("del_me") is None
    assert await repo.delete("del_me") is False
