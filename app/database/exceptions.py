"""Domain exceptions for database and persistence operations."""

from __future__ import annotations


class PersistenceError(Exception):
    """Base exception for all persistence-related errors."""


class GameNotFoundError(PersistenceError):
    """Raised when a requested game does not exist in the database."""


class GameAlreadyExistsError(PersistenceError):
    """Raised when attempting to insert a game record with an existing game_id."""


class VersionConflictError(PersistenceError):
    """Raised when optimistic concurrency control detects a version mismatch."""


class InvalidPersistedStateError(PersistenceError):
    """Raised when a persisted snapshot is corrupt or fails validation."""


class DatabaseOperationError(PersistenceError):
    """Raised when an unexpected database error occurs during an operation."""


class InvalidLifecycleTransitionError(PersistenceError):
    """Raised when an invalid game lifecycle transition is attempted."""
