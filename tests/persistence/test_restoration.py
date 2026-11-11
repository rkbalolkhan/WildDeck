"""Comprehensive tests for state restoration across all Phase 02 and Phase 03 mechanics."""

from __future__ import annotations

import pytest

from app.database.session import Database
from app.engine.card import CardColor, CardType
from app.engine.deck import Deck
from app.engine.game import Game
from app.engine.player import Player
from app.engine.state import Direction, GameConfig, GameRules, GameStatus
from app.services.persistence import GamePersistenceService
from tests.engine_helpers import B, G, R, Y, make_game, num, wd4


@pytest.mark.asyncio
async def test_restore_advanced_phase03_state(db: Database) -> None:
    service = GamePersistenceService(db)

    # Setup a game with stacking enabled, WDF challenge enabled, custom match score
    rules = GameRules(
        stacking_enabled=True,
        stack_draw_two=True,
        stack_wild_draw_four=True,
        allow_mixed_stacking=True,
        wild_draw_four_challenge=True,
        scoring_enabled=True,
        match_target_score=250,
    )
    cfg = GameConfig(rules=rules)

    p1 = Player(user_id=100, name="Alice", hand=[num(R, 5), wd4()])
    p2 = Player(user_id=101, name="Bob", hand=[num(G, 5), num(B, 5)])
    p3 = Player(user_id=102, name="Charlie", hand=[num(Y, 5)])

    draw_pile = [num(R, 1), num(G, 2), num(B, 3)]
    c_top = num(R, 9)
    discard_pile = [c_top]
    deck = Deck(draw_pile=draw_pile, discard_pile=discard_pile)

    game = Game(
        game_id="adv_g1",
        players=[p1, p2, p3],
        deck=deck,
        config=cfg,
        rng=None,
        status=GameStatus.ACTIVE,
        current_index=1,
        direction=Direction.COUNTERCLOCKWISE,
        active_color=CardColor.GREEN,
        drawn_card_id=None,
        uno_declarations={102: True},
        uno_vulnerable={101: 1},
        pending_penalty={
            "type": CardType.DRAW_TWO,
            "count": 4,
            "target_player_id": 101,
        },
        pending_challenge={
            "challenger_id": 101,
            "offender_id": 100,
            "card_id": "c_wdf_dummy",
            "offender_hand_snapshot": [{"id": "c1", "color": "red", "type": "number", "value": 5}],
            "previous_color": CardColor.RED,
        },
        round_scores={100: 45, 101: 20, 102: 0},
        match_scores={100: 120, 101: 80, 102: 30},
    )
    game._uno_window_player_id = 102

    # Save to database
    await service.create_game(game)

    # Restore from database
    restored_wrapper = await service.restore_game("adv_g1")
    restored = restored_wrapper.game

    # Verify structural integrity
    restored.validate_integrity(expected_total=None)

    # 1. Players and hand contents
    assert restored.player_ids == [100, 101, 102]
    assert [c.id for c in restored.get_player(100).hand] == [c.id for c in p1.hand]
    assert [c.id for c in restored.get_player(101).hand] == [c.id for c in p2.hand]
    assert [c.id for c in restored.get_player(102).hand] == [c.id for c in p3.hand]

    # 2. Deck order
    assert [c.id for c in restored.deck.draw_pile] == [c.id for c in draw_pile]
    assert [c.id for c in restored.deck.discard_pile] == [c.id for c in discard_pile]
    assert restored.top_card.id == c_top.id

    # 3. Turn, direction, active color
    assert restored.current_index == 1
    assert restored.direction == Direction.COUNTERCLOCKWISE
    assert restored.active_color == CardColor.GREEN

    # 4. UNO state
    assert restored.uno_declarations == {102: True}
    assert restored.uno_vulnerable == {101: 1}
    assert restored._uno_window_player_id == 102

    # 5. Pending penalty and stacking
    assert restored.pending_penalty is not None
    assert restored.pending_penalty["type"] == CardType.DRAW_TWO
    assert restored.pending_penalty["count"] == 4
    assert restored.pending_penalty["target_player_id"] == 101

    # 6. Pending challenge
    assert restored.pending_challenge is not None
    assert restored.pending_challenge["challenger_id"] == 101
    assert restored.pending_challenge["previous_color"] == CardColor.RED

    # 7. Scores and match standings
    assert restored.round_scores == {100: 45, 101: 20, 102: 0}
    assert restored.match_scores == {100: 120, 101: 80, 102: 30}
    assert restored.config.rules.match_target_score == 250


@pytest.mark.asyncio
async def test_restored_gameplay_actions_execute_correctly(db: Database) -> None:
    service = GamePersistenceService(db)

    # Create a 2-player game where player 1 can play a card
    c_play = num(R, 7)
    c_top = num(R, 3)

    game = make_game([[c_play], [num(G, 8)]], c_top, current=0)
    await service.create_game(game)

    restored_obj = await service.restore_game(game.game_id)
    restored = restored_obj.game

    # Player 1 plays their last card, winning the game
    restored.play_card(100, c_play.id)
    assert restored.status == GameStatus.FINISHED
    assert restored.winner_id == 100

    # Save final game state
    saved = await service.save_game(restored, current_version=restored_obj.version)
    assert saved.status.value == "completed"
    assert saved.winner_id == 100
    assert saved.completed_at is not None


@pytest.mark.asyncio
async def test_restored_game_challenge_wild_draw_four(db: Database) -> None:
    service = GamePersistenceService(db)

    # Offender played WDF illegally because they had previous color (RED)
    offender_hand = [num(R, 5)]
    challenger_hand = [num(G, 2)]
    wdf_card = wd4()

    game = make_game(
        [offender_hand, challenger_hand],
        wdf_card,
        active_color=CardColor.BLUE,
        current=1,  # challenger's turn
    )
    game.pending_challenge = {
        "challenger_id": 101,
        "offender_id": 100,
        "card_id": wdf_card.id,
        "offender_hand_snapshot": [c.to_dict() for c in offender_hand],
        "previous_color": CardColor.RED,
    }
    game.pending_penalty = {
        "type": CardType.WILD_DRAW_FOUR,
        "count": 4,
        "target_player_id": 101,
    }

    await service.create_game(game)

    # Restore and challenge
    restored_obj = await service.restore_game(game.game_id)
    restored = restored_obj.game

    events = restored.challenge_wild_draw_four(101)
    # Challenge succeeded because offender held red card
    assert any(e.type.value == "wild_draw_four_challenge_succeeded" for e in events)
    assert restored.pending_challenge is None
    # Offender drew penalty
    assert restored.get_player(100).hand_size > len(offender_hand)
