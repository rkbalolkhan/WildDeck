"""Asynchronous repository for persistent game records."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.exceptions import (
    DatabaseOperationError,
    GameAlreadyExistsError,
    GameNotFoundError,
    InvalidLifecycleTransitionError,
    VersionConflictError,
)
from app.database.models.game import (
    GameLifecycle,
    GameRecord,
    validate_lifecycle_transition,
)


class GameRepository:
    """Performs all persistence operations on game records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, record: GameRecord) -> GameRecord:
        """Insert a new game record; raises if game_id already exists."""
        self.session.add(record)
        try:
            await self.session.flush()
            await self.session.refresh(record)
            return record
        except IntegrityError as exc:
            await self.session.rollback()
            raise GameAlreadyExistsError(f"Game with ID '{record.game_id}' already exists") from exc
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise DatabaseOperationError(f"Failed to create game: {exc!r}") from exc

    async def get_by_id(self, internal_id: int) -> GameRecord | None:
        """Retrieve a game by internal primary key."""
        try:
            return await self.session.get(GameRecord, internal_id)
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                f"Failed to fetch game by ID {internal_id}: {exc!r}"
            ) from exc

    async def get_by_game_id(self, game_id: str) -> GameRecord | None:
        """Retrieve a game by its unique public game_id."""
        try:
            stmt = select(GameRecord).where(GameRecord.game_id == game_id)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                f"Failed to fetch game by game_id '{game_id}': {exc!r}"
            ) from exc

    async def get_by_status(
        self, status: GameLifecycle | Sequence[GameLifecycle]
    ) -> list[GameRecord]:
        """Retrieve games matching given status or statuses."""
        statuses = [status] if isinstance(status, GameLifecycle) else list(status)
        try:
            stmt = (
                select(GameRecord)
                .where(GameRecord.status.in_(statuses))
                .order_by(GameRecord.created_at)
            )
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(f"Failed to fetch games by status: {exc!r}") from exc

    async def get_active_games(self) -> list[GameRecord]:
        """Convenience method returning all currently ACTIVE games."""
        return await self.get_by_status(GameLifecycle.ACTIVE)

    async def save_snapshot(
        self,
        game_id: str,
        *,
        state: dict[str, Any],
        current_version: int,
        status: GameLifecycle | None = None,
        winner_id: int | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> GameRecord:
        """Update game state and version using optimistic concurrency control."""
        existing = await self.get_by_game_id(game_id)
        if existing is None:
            raise GameNotFoundError(f"Game '{game_id}' not found")
        if existing.status in (GameLifecycle.COMPLETED, GameLifecycle.CANCELLED):
            raise InvalidLifecycleTransitionError(
                f"Cannot update state for game '{game_id}' in "
                f"terminal lifecycle '{existing.status.value}'"
            )
        if existing.version != current_version:
            raise VersionConflictError(
                f"Game '{game_id}' version conflict: "
                f"expected {current_version}, actual is {existing.version}"
            )

        try:
            values: dict[str, Any] = {
                "state": state,
                "version": current_version + 1,
                "updated_at": datetime.now(UTC),
            }
            if status is not None:
                values["status"] = status
            if winner_id is not None:
                values["winner_id"] = winner_id
            if started_at is not None:
                values["started_at"] = started_at
            if completed_at is not None:
                values["completed_at"] = completed_at

            stmt = (
                update(GameRecord)
                .where(GameRecord.game_id == game_id, GameRecord.version == current_version)
                .values(**values)
            )
            result = await self.session.execute(stmt)

            if result.rowcount == 0:
                # Re-check under race condition
                current = await self.get_by_game_id(game_id)
                if current is None:
                    raise GameNotFoundError(f"Game '{game_id}' not found")
                raise VersionConflictError(
                    f"Game '{game_id}' version conflict: "
                    f"expected {current_version}, actual is {current.version}"
                )

            await self.session.flush()
            updated = await self.get_by_game_id(game_id)
            if updated is None:
                raise GameNotFoundError(f"Game '{game_id}' not found after update")
            return updated
        except (GameNotFoundError, VersionConflictError, InvalidLifecycleTransitionError):
            raise
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(f"Failed to update game snapshot: {exc!r}") from exc

    async def update_lifecycle(
        self,
        game_id: str,
        *,
        new_status: GameLifecycle,
        current_version: int,
        winner_id: int | None = None,
    ) -> GameRecord:
        """Transition game to a new lifecycle state with validation and optimistic concurrency."""
        existing = await self.get_by_game_id(game_id)
        if existing is None:
            raise GameNotFoundError(f"Game '{game_id}' not found")

        validate_lifecycle_transition(existing.status, new_status)

        now = datetime.now(UTC)
        started_at = (
            now if new_status == GameLifecycle.ACTIVE and existing.started_at is None else None
        )
        completed_at = (
            now if new_status in (GameLifecycle.COMPLETED, GameLifecycle.CANCELLED) else None
        )

        return await self.save_snapshot(
            game_id,
            state=existing.state,
            current_version=current_version,
            status=new_status,
            winner_id=winner_id,
            started_at=started_at,
            completed_at=completed_at,
        )

    async def mark_started(self, game_id: str, current_version: int) -> GameRecord:
        """Mark game as ACTIVE."""
        return await self.update_lifecycle(
            game_id, new_status=GameLifecycle.ACTIVE, current_version=current_version
        )

    async def mark_completed(
        self, game_id: str, current_version: int, winner_id: int | None = None
    ) -> GameRecord:
        """Mark game as COMPLETED."""
        return await self.update_lifecycle(
            game_id,
            new_status=GameLifecycle.COMPLETED,
            current_version=current_version,
            winner_id=winner_id,
        )

    async def mark_cancelled(self, game_id: str, current_version: int) -> GameRecord:
        """Mark game as CANCELLED."""
        return await self.update_lifecycle(
            game_id, new_status=GameLifecycle.CANCELLED, current_version=current_version
        )

    async def delete(self, game_id: str) -> bool:
        """Delete a game record by game_id; returns True if deleted."""
        try:
            stmt = delete(GameRecord).where(GameRecord.game_id == game_id)
            result = await self.session.execute(stmt)
            await self.session.flush()
            return result.rowcount > 0
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(f"Failed to delete game '{game_id}': {exc!r}") from exc
