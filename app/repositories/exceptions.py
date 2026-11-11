"""Re-export persistence exceptions for the repository layer."""

from __future__ import annotations

from app.database.exceptions import (
    DatabaseOperationError,
    GameAlreadyExistsError,
    GameNotFoundError,
    InvalidLifecycleTransitionError,
    InvalidPersistedStateError,
    PersistenceError,
    VersionConflictError,
)

__all__ = [
    "DatabaseOperationError",
    "GameAlreadyExistsError",
    "GameNotFoundError",
    "InvalidLifecycleTransitionError",
    "InvalidPersistedStateError",
    "PersistenceError",
    "VersionConflictError",
]
