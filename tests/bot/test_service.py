"""Unit tests for TelegramGameService."""

import pytest

from app.database.models.game import GameLifecycle
from app.services.telegram_game import (
    GameAlreadyExistsError,
    GameNotFoundError,
    TelegramGameService,
    UnauthorizedActionError,
)


@pytest.mark.asyncio
async def test_create_and_get_active_game(telegram_game_service: TelegramGameService) -> None:
    chat_id = -100123
    record, game = await telegram_game_service.create_game(
        chat_id=chat_id,
        chat_type="group",
        user_id=1,
        user_name="Alice",
    )

    assert record.game_id.startswith("uno_")
    assert record.status == GameLifecycle.CREATED
    assert record.state["telegram"]["chat_id"] == chat_id
    assert record.state["telegram"]["creator_id"] == 1
    assert game.players[0].name == "Alice"

    # Fetch active game
    active = await telegram_game_service.get_active_game_for_chat(chat_id)
    assert active is not None
    assert active.game_id == record.game_id


@pytest.mark.asyncio
async def test_duplicate_game_in_same_chat_prevented(
    telegram_game_service: TelegramGameService,
) -> None:
    chat_id = -100456
    await telegram_game_service.create_game(
        chat_id=chat_id,
        chat_type="supergroup",
        user_id=1,
        user_name="Alice",
    )

    with pytest.raises(GameAlreadyExistsError) as exc_info:
        await telegram_game_service.create_game(
            chat_id=chat_id,
            chat_type="supergroup",
            user_id=2,
            user_name="Bob",
        )
    assert "already in progress" in str(exc_info.value)


@pytest.mark.asyncio
async def test_cancel_game_by_creator(telegram_game_service: TelegramGameService) -> None:
    chat_id = -100789
    record, _ = await telegram_game_service.create_game(
        chat_id=chat_id,
        chat_type="group",
        user_id=10,
        user_name="Alice",
    )

    # Cancelled by creator
    cancelled = await telegram_game_service.cancel_game(
        chat_id=chat_id,
        user_id=10,
        is_admin=False,
    )
    assert cancelled.status == GameLifecycle.CANCELLED

    # Active game should now be None
    active = await telegram_game_service.get_active_game_for_chat(chat_id)
    assert active is None


@pytest.mark.asyncio
async def test_cancel_game_by_admin(telegram_game_service: TelegramGameService) -> None:
    chat_id = -100790
    await telegram_game_service.create_game(
        chat_id=chat_id,
        chat_type="group",
        user_id=10,
        user_name="Alice",
    )

    # Cancelled by chat admin who is not the creator
    cancelled = await telegram_game_service.cancel_game(
        chat_id=chat_id,
        user_id=999,
        is_admin=True,
    )
    assert cancelled.status == GameLifecycle.CANCELLED


@pytest.mark.asyncio
async def test_cancel_game_by_unauthorized_user(telegram_game_service: TelegramGameService) -> None:
    chat_id = -100791
    await telegram_game_service.create_game(
        chat_id=chat_id,
        chat_type="group",
        user_id=10,
        user_name="Alice",
    )

    # Attempt to cancel by a regular user who didn't create the game
    with pytest.raises(UnauthorizedActionError):
        await telegram_game_service.cancel_game(
            chat_id=chat_id,
            user_id=555,
            is_admin=False,
        )


@pytest.mark.asyncio
async def test_cancel_game_not_found(telegram_game_service: TelegramGameService) -> None:
    with pytest.raises(GameNotFoundError):
        await telegram_game_service.cancel_game(
            chat_id=-999999,
            user_id=1,
            is_admin=False,
        )


@pytest.mark.asyncio
async def test_can_create_new_game_after_cancellation(
    telegram_game_service: TelegramGameService,
) -> None:
    chat_id = -100888
    record1, _ = await telegram_game_service.create_game(
        chat_id=chat_id,
        chat_type="group",
        user_id=1,
        user_name="Alice",
    )
    await telegram_game_service.cancel_game(chat_id=chat_id, user_id=1)

    # Now creating a new game in the same chat should succeed
    record2, _ = await telegram_game_service.create_game(
        chat_id=chat_id,
        chat_type="group",
        user_id=2,
        user_name="Bob",
    )
    assert record2.game_id != record1.game_id
    assert record2.status == GameLifecycle.CREATED
