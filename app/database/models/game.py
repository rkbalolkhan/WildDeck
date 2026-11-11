"""Persistent game record model and lifecycle definitions."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.exceptions import InvalidLifecycleTransitionError


class GameLifecycle(enum.StrEnum):
    CREATED = "created"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


LIFECYCLE_TRANSITIONS: dict[GameLifecycle, set[GameLifecycle]] = {
    GameLifecycle.CREATED: {GameLifecycle.ACTIVE, GameLifecycle.CANCELLED},
    GameLifecycle.ACTIVE: {GameLifecycle.COMPLETED, GameLifecycle.CANCELLED},
    GameLifecycle.COMPLETED: set(),
    GameLifecycle.CANCELLED: set(),
}


def validate_lifecycle_transition(current: GameLifecycle, target: GameLifecycle) -> None:
    """Validate game lifecycle transition; raise if invalid."""
    if target == current:
        return
    allowed = LIFECYCLE_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidLifecycleTransitionError(
            f"Cannot transition game from '{current.value}' to '{target.value}'"
        )


JSONBType = JSONB().with_variant(JSON(), "sqlite")


class GameRecord(Base):
    """Database model storing persistent UNO game records."""

    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    status: Mapped[GameLifecycle] = mapped_column(
        Enum(GameLifecycle, name="game_lifecycle", native_enum=False, length=32),
        nullable=False,
        default=GameLifecycle.CREATED,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    state: Mapped[dict[str, Any]] = mapped_column(JSONBType, nullable=False)
    winner_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
