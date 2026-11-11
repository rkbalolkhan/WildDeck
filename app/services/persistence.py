"""Persistence service translating between the UNO engine and persistent database records."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.exceptions import (
    GameNotFoundError,
    InvalidLifecycleTransitionError,
    InvalidPersistedStateError,
)
from app.database.models.game import (
    GameLifecycle,
    GameRecord,
)
from app.database.session import Database
from app.engine.errors import GameError
from app.engine.game import Game
from app.engine.state import GameStatus
from app.repositories.game import GameRepository

logger = logging.getLogger(__name__)

STATUS_TO_LIFECYCLE: dict[GameStatus, GameLifecycle] = {
    GameStatus.WAITING: GameLifecycle.CREATED,
    GameStatus.ACTIVE: GameLifecycle.ACTIVE,
    GameStatus.FINISHED: GameLifecycle.COMPLETED,
    GameStatus.CANCELLED: GameLifecycle.CANCELLED,
}

LIFECYCLE_TO_STATUS: dict[GameLifecycle, GameStatus] = {
    GameLifecycle.CREATED: GameStatus.WAITING,
    GameLifecycle.ACTIVE: GameStatus.ACTIVE,
    GameLifecycle.COMPLETED: GameStatus.FINISHED,
    GameLifecycle.CANCELLED: GameStatus.CANCELLED,
}


@dataclass(frozen=True)
class RestoredGame:
    """Represents a restored engine game with persistence metadata."""

    game: Game
    version: int
    lifecycle: GameLifecycle


@dataclass(frozen=True)
class FailedRecovery:
    """Details of a game record that failed recovery."""

    game_id: str
    error_category: str
    error_message: str


@dataclass(frozen=True)
class RecoveryReport:
    """Result of an active game recovery run."""

    restored: list[RestoredGame]
    failed: list[FailedRecovery]


class GamePersistenceService:
    """High-level service managing game persistence, restoration, and recovery."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def _resolve_lifecycle(self, game: Game) -> GameLifecycle:
        return STATUS_TO_LIFECYCLE.get(game.status, GameLifecycle.ACTIVE)

    async def create_game(self, game: Game, *, session: AsyncSession | None = None) -> GameRecord:
        """Create and persist a new game record from an engine game."""
        lifecycle = self._resolve_lifecycle(game)
        now = datetime.now(UTC)
        started_at = now if lifecycle == GameLifecycle.ACTIVE else None
        completed_at = (
            now if lifecycle in (GameLifecycle.COMPLETED, GameLifecycle.CANCELLED) else None
        )

        record = GameRecord(
            game_id=game.game_id,
            status=lifecycle,
            version=1,
            state=game.to_dict(),
            winner_id=game.winner_id,
            started_at=started_at,
            completed_at=completed_at,
        )

        if session is not None:
            repo = GameRepository(session)
            return await repo.create(record)

        async with self.db.session() as sess:
            repo = GameRepository(sess)
            return await repo.create(record)

    async def save_game(
        self, game: Game, current_version: int, *, session: AsyncSession | None = None
    ) -> GameRecord:
        """Save the current state of an engine game under optimistic concurrency control."""
        lifecycle = self._resolve_lifecycle(game)
        now = datetime.now(UTC)
        completed_at = (
            now if lifecycle in (GameLifecycle.COMPLETED, GameLifecycle.CANCELLED) else None
        )

        if session is not None:
            repo = GameRepository(session)
            return await repo.save_snapshot(
                game.game_id,
                state=game.to_dict(),
                current_version=current_version,
                status=lifecycle,
                winner_id=game.winner_id,
                completed_at=completed_at,
            )

        async with self.db.session() as sess:
            repo = GameRepository(sess)
            return await repo.save_snapshot(
                game.game_id,
                state=game.to_dict(),
                current_version=current_version,
                status=lifecycle,
                winner_id=game.winner_id,
                completed_at=completed_at,
            )

    async def load_game(self, game_id: str, *, session: AsyncSession | None = None) -> RestoredGame:
        """Load and deserialize any game from database regardless of lifecycle."""
        if session is not None:
            repo = GameRepository(session)
            record = await repo.get_by_game_id(game_id)
        else:
            async with self.db.session() as sess:
                repo = GameRepository(sess)
                record = await repo.get_by_game_id(game_id)

        if record is None:
            raise GameNotFoundError(f"Game '{game_id}' not found")

        try:
            game = Game.from_dict(record.state)
        except (GameError, ValueError, KeyError, TypeError) as exc:
            raise InvalidPersistedStateError(
                f"Failed to deserialize game '{game_id}': {exc!r}"
            ) from exc

        return RestoredGame(game=game, version=record.version, lifecycle=record.status)

    async def restore_game(
        self, game_id: str, *, session: AsyncSession | None = None
    ) -> RestoredGame:
        """Restore an ACTIVE game for gameplay; raises if game is completed or cancelled."""
        restored = await self.load_game(game_id, session=session)
        if restored.lifecycle != GameLifecycle.ACTIVE:
            raise InvalidLifecycleTransitionError(
                f"Cannot restore game '{game_id}' with "
                f"non-active lifecycle '{restored.lifecycle.value}'"
            )
        return restored

    async def update_lifecycle(
        self,
        game_id: str,
        new_status: GameLifecycle,
        current_version: int,
        *,
        winner_id: int | None = None,
        session: AsyncSession | None = None,
    ) -> GameRecord:
        """Update a game's lifecycle state with transition checks and concurrency protection."""
        if session is not None:
            repo = GameRepository(session)
            return await repo.update_lifecycle(
                game_id,
                new_status=new_status,
                current_version=current_version,
                winner_id=winner_id,
            )

        async with self.db.session() as sess:
            repo = GameRepository(sess)
            return await repo.update_lifecycle(
                game_id,
                new_status=new_status,
                current_version=current_version,
                winner_id=winner_id,
            )

    async def recover_active_games(self, *, session: AsyncSession | None = None) -> RecoveryReport:
        """Find and deserialize all active games; report corrupt entries without failing."""
        if session is not None:
            repo = GameRepository(session)
            records = await repo.get_active_games()
        else:
            async with self.db.session() as sess:
                repo = GameRepository(sess)
                records = await repo.get_active_games()

        restored_list: list[RestoredGame] = []
        failed_list: list[FailedRecovery] = []

        for record in records:
            try:
                game = Game.from_dict(record.state)
                restored_list.append(
                    RestoredGame(
                        game=game,
                        version=record.version,
                        lifecycle=record.status,
                    )
                )
            except Exception as exc:
                err_category = exc.__class__.__name__
                err_message = str(exc)
                logger.warning(
                    "Corrupted active game skipped during recovery",
                    extra={
                        "game_id": record.game_id,
                        "error_category": err_category,
                    },
                )
                failed_list.append(
                    FailedRecovery(
                        game_id=record.game_id,
                        error_category=err_category,
                        error_message=err_message,
                    )
                )

        return RecoveryReport(restored=restored_list, failed=failed_list)
