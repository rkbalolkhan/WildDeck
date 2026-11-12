"""Telegram-specific game orchestration service.

Bridges Aiogram handlers, the UNO engine, and Phase 04 database persistence.
"""

from __future__ import annotations

import logging
import random
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.game import GameLifecycle, GameRecord
from app.database.session import Database
from app.engine.deck import Deck
from app.engine.game import Game
from app.engine.player import Player
from app.engine.state import GameConfig, GameStatus
from app.repositories.game import GameRepository
from app.services.persistence import GamePersistenceService

logger = logging.getLogger(__name__)


class TelegramGameError(Exception):
    """Base exception for Telegram game service operations."""


class GameAlreadyExistsError(TelegramGameError):
    """An active or pending game already exists in this chat."""

    def __init__(self, message: str, game_id: str | None = None) -> None:
        super().__init__(message)
        self.game_id = game_id


class GameNotFoundError(TelegramGameError):
    """No active or matching game was found."""


class UnauthorizedActionError(TelegramGameError):
    """User lacks permission to perform the requested game operation."""


class InvalidGameOperationError(TelegramGameError):
    """Requested operation cannot be completed due to invalid game state."""


class TelegramGameService:
    """Coordinates Telegram chat games with persistence and engine rules."""

    def __init__(self, db: Database, persistence: GamePersistenceService | None = None) -> None:
        self.db = db
        self.persistence = persistence or GamePersistenceService(db)

    async def get_active_game_for_chat(
        self, chat_id: int, *, session: AsyncSession | None = None
    ) -> GameRecord | None:
        """Find the currently pending or active game associated with a Telegram chat."""
        active_lifecycles = (GameLifecycle.CREATED, GameLifecycle.ACTIVE)

        if session is not None:
            repo = GameRepository(session)
            records = await repo.get_by_status(active_lifecycles)
        else:
            async with self.db.session() as sess:
                repo = GameRepository(sess)
                records = await repo.get_by_status(active_lifecycles)

        for record in records:
            meta = record.state.get("telegram")
            if isinstance(meta, dict) and meta.get("chat_id") == chat_id:
                return record
        return None

    async def get_game_by_id(
        self, game_id: str, *, session: AsyncSession | None = None
    ) -> GameRecord | None:
        """Retrieve a game record by its unique public game_id."""
        if session is not None:
            repo = GameRepository(session)
            return await repo.get_by_game_id(game_id)

        async with self.db.session() as sess:
            repo = GameRepository(sess)
            return await repo.get_by_game_id(game_id)

    async def create_game(
        self,
        *,
        chat_id: int,
        chat_type: str,
        user_id: int,
        user_name: str,
        thread_id: int | None = None,
        config: GameConfig | None = None,
        session: AsyncSession | None = None,
    ) -> tuple[GameRecord, Game]:
        """Create and persist a new UNO game in WAITING status for a Telegram chat.

        Raises:
            GameAlreadyExistsError: If an active game already exists in this chat.
        """

        async def _execute(sess: AsyncSession) -> tuple[GameRecord, Game]:
            existing = await self.get_active_game_for_chat(chat_id, session=sess)
            if existing is not None:
                raise GameAlreadyExistsError(
                    f"An active game is already in progress in this chat (ID: {existing.game_id})",
                    game_id=existing.game_id,
                )

            game_id = f"uno_{uuid.uuid4().hex[:12]}"
            creator = Player(user_id=user_id, name=user_name)
            game_config = config or GameConfig()
            deck = Deck.standard()

            game = Game(
                game_id=game_id,
                players=[creator],
                deck=deck,
                config=game_config,
                rng=random.Random(),
                status=GameStatus.WAITING,
            )

            state_dict = game.to_dict()
            state_dict["telegram"] = {
                "chat_id": chat_id,
                "chat_type": chat_type,
                "creator_id": user_id,
                "creator_name": user_name,
                "thread_id": thread_id,
            }

            record = GameRecord(
                game_id=game_id,
                status=GameLifecycle.CREATED,
                version=1,
                state=state_dict,
                winner_id=None,
            )

            repo = GameRepository(sess)
            persisted = await repo.create(record)
            logger.info("Created game %s for chat %s by user %s", game_id, chat_id, user_id)
            return persisted, game

        if session is not None:
            return await _execute(session)

        async with self.db.session() as sess:
            return await _execute(sess)

    async def cancel_game(
        self,
        *,
        chat_id: int,
        user_id: int,
        is_admin: bool = False,
        session: AsyncSession | None = None,
    ) -> GameRecord:
        """Cancel an active or pending game in a chat.

        Only the game creator or a chat administrator is authorized.

        Raises:
            GameNotFoundError: If no active game exists for this chat.
            UnauthorizedActionError: If the caller is not the creator or an admin.
        """

        async def _execute(sess: AsyncSession) -> GameRecord:
            record = await self.get_active_game_for_chat(chat_id, session=sess)
            if record is None:
                raise GameNotFoundError(f"No active game found in chat {chat_id}")

            telegram_meta = record.state.get("telegram") or {}
            creator_id = telegram_meta.get("creator_id")

            if creator_id is not None and user_id != creator_id and not is_admin:
                raise UnauthorizedActionError(
                    "Only the game creator or chat administrators can cancel this game."
                )

            updated = await self.persistence.update_lifecycle(
                record.game_id,
                GameLifecycle.CANCELLED,
                record.version,
                session=sess,
            )
            logger.info("Cancelled game %s in chat %s by user %s", record.game_id, chat_id, user_id)
            return updated

        if session is not None:
            return await _execute(session)

        async with self.db.session() as sess:
            return await _execute(sess)

    async def get_game_status(
        self, chat_id: int, *, session: AsyncSession | None = None
    ) -> tuple[GameRecord, Game | None]:
        """Fetch the active game record and restored Game instance for a chat.

        Raises:
            GameNotFoundError: If no active game exists in this chat.
        """
        record = await self.get_active_game_for_chat(chat_id, session=session)
        if record is None:
            raise GameNotFoundError(f"No active game found in chat {chat_id}")

        game: Game | None = None
        try:
            game = Game.from_dict(record.state)
        except Exception as exc:
            logger.warning("Failed to restore Game instance for %s: %s", record.game_id, exc)

        return record, game
