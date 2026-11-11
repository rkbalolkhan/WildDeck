"""ORM models registration for Alembic and application queries."""

from app.database.models.game import (
    LIFECYCLE_TRANSITIONS,
    GameLifecycle,
    GameRecord,
    validate_lifecycle_transition,
)

__all__ = [
    "GameLifecycle",
    "GameRecord",
    "LIFECYCLE_TRANSITIONS",
    "validate_lifecycle_transition",
]
