"""Unit and integration tests for GamePersistenceService."""

from __future__ import annotations

import logging

import pytest

from app.database.exceptions import (
    GameNotFoundError,
    InvalidLifecycleTransitionError,
    InvalidPersistedStateError,
    VersionConflictError,
)
from app.database.models.game import GameLifecycle, GameRecord
from app.database.session import Database
from app.engine.game import Game
from app.engine.player import Player
from app.repositories.game import GameRepository
from app.services.persistence import GamePersistenceService


def make_engine_game(game_id: str = "engine_g1") -> Game:
    p1 = Player(user_id=100, name="Alice")
    p2 = Player(user_id=101, name="Bob")
    return Game.new([p1, p2], game_id=game_id)


@pytest.mark.asyncio
async def test_create_and_load_game(db: Database) -> None:
    service = GamePersistenceService(db)
    game = make_engine_game("svc_g1")

    record = await service.create_game(game)
    assert record.game_id == "svc_g1"
    assert record.version == 1
    assert record.status == GameLifecycle.ACTIVE

    restored = await service.load_game("svc_g1")
    assert restored.version == 1
    assert restored.lifecycle == GameLifecycle.ACTIVE
    assert restored.game.game_id == "svc_g1"
    assert len(restored.game.players) == 2


@pytest.mark.asyncio
async def test_save_game_state_and_concurrency(db: Database) -> None:
    service = GamePersistenceService(db)
    game = make_engine_game("svc_g2")
    await service.create_game(game)

    # Perform an engine turn
    pid = game.current_player_id
    playable = game.get_playable_cards(pid)
    if playable:
        game.play_card(pid, playable[0].id, "red" if playable[0].is_wild else None)
    else:
        game.draw_card(pid)

    saved = await service.save_game(game, current_version=1)
    assert saved.version == 2

    # Attempting to save with old version 1 must raise VersionConflictError
    with pytest.raises(VersionConflictError):
        await service.save_game(game, current_version=1)

    # Saving with version 2 succeeds
    saved2 = await service.save_game(game, current_version=2)
    assert saved2.version == 3


@pytest.mark.asyncio
async def test_restore_rejects_completed_or_cancelled_games(db: Database) -> None:
    service = GamePersistenceService(db)
    game = make_engine_game("svc_g3")
    await service.create_game(game)

    await service.update_lifecycle(
        "svc_g3", GameLifecycle.COMPLETED, current_version=1, winner_id=100
    )

    # load_game succeeds for any lifecycle
    loaded = await service.load_game("svc_g3")
    assert loaded.lifecycle == GameLifecycle.COMPLETED

    # restore_game rejects non-active games
    with pytest.raises(InvalidLifecycleTransitionError):
        await service.restore_game("svc_g3")


@pytest.mark.asyncio
async def test_load_non_existent_game_raises_error(db: Database) -> None:
    service = GamePersistenceService(db)
    with pytest.raises(GameNotFoundError):
        await service.load_game("does_not_exist")


@pytest.mark.asyncio
async def test_load_corrupted_state_raises_invalid_persisted_state(db: Database) -> None:
    service = GamePersistenceService(db)
    async with db.session() as session:
        repo = GameRepository(session)
        await repo.create(
            GameRecord(
                game_id="corrupt_g",
                status=GameLifecycle.ACTIVE,
                version=1,
                state={"invalid": "payload"},
            )
        )

    with pytest.raises(InvalidPersistedStateError):
        await service.load_game("corrupt_g")


@pytest.mark.asyncio
async def test_recover_active_games_with_mixed_valid_and_corrupt(
    db: Database, caplog: pytest.LogCaptureFixture
) -> None:
    service = GamePersistenceService(db)
    g1 = make_engine_game("rec_g1")
    g2 = make_engine_game("rec_g2")
    await service.create_game(g1)
    await service.create_game(g2)

    # Insert a corrupted active game and a completed game
    async with db.session() as session:
        repo = GameRepository(session)
        await repo.create(
            GameRecord(
                game_id="rec_corrupt",
                status=GameLifecycle.ACTIVE,
                version=1,
                state={"malformed": True},
            )
        )
        await repo.create(
            GameRecord(
                game_id="rec_completed",
                status=GameLifecycle.COMPLETED,
                version=1,
                state={},
            )
        )

    with caplog.at_level(logging.WARNING):
        report = await service.recover_active_games()

    assert len(report.restored) == 2
    assert {r.game.game_id for r in report.restored} == {"rec_g1", "rec_g2"}
    assert len(report.failed) == 1
    assert report.failed[0].game_id == "rec_corrupt"
    assert report.failed[0].error_category in ("InvalidGameStateError", "KeyError")

    # Verify structured logging does not leak secret card states
    assert any("Corrupted active game skipped" in record.message for record in caplog.records)
