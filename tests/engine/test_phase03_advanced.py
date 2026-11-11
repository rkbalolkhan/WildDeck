import random

from app.engine import CardColor, Game, GameConfig, GameRules, GameStatus, Player
from tests.engine_helpers import B, R, num, wd4


def test_playing_last_wild_draw_four_blocks_immediate_finish_until_challenge() -> None:
    offender = Player(100, "Offender", [wd4()])
    challenger = Player(101, "Challenger", [num(R, 1)])
    game = Game(
        game_id="g",
        players=[offender, challenger],
        deck=__import__("app.engine.deck", fromlist=["Deck"]).Deck(
            [num(B, 2), num(B, 3), num(B, 4), num(B, 5)],
            [num(R, 7)],
            rng=random.Random(0),
        ),
        config=GameConfig(rules=GameRules(wild_draw_four_challenge=True)),
        rng=random.Random(0),
        status=GameStatus.ACTIVE,
        current_index=0,
        active_color=CardColor.RED,
    )

    events = game.play_card(100, offender.hand[0].id, CardColor.RED)

    assert game.status is GameStatus.ACTIVE
    assert game.winner_id is None
    assert game.pending_challenge is not None
    assert not any(event.type.value == "game_finished" for event in events)
    assert game.get_player(101).hand_size == 1


def test_wild_draw_four_challenge_uses_offender_hand() -> None:
    offender = Player(100, "Offender", [num(R, 5)])
    challenger = Player(101, "Challenger", [num(B, 7)])
    game = Game(
        game_id="g",
        players=[offender, challenger],
        deck=__import__("app.engine.deck", fromlist=["Deck"]).Deck(
            [num(R, 1), num(R, 2), num(R, 3), num(R, 4)],
            [num(B, 8)],
            rng=random.Random(0),
        ),
        config=GameConfig(),
        rng=random.Random(0),
        status=GameStatus.ACTIVE,
        current_index=0,
        active_color=CardColor.RED,
    )
    game.pending_challenge = {
        "challenger_id": 101,
        "offender_id": 100,
        "card_id": offender.hand[0].id,
        "offender_hand_snapshot": [offender.hand[0].id],
        "previous_color": CardColor.RED,
    }

    events = game.challenge_wild_draw_four(101)

    assert any(event.type.value == "wild_draw_four_challenge_succeeded" for event in events)
    assert len(offender.hand) == 5
    assert len(challenger.hand) == 1


def test_uno_catch_applies_one_penalty_and_clears_vulnerability() -> None:
    target = Player(100, "Target", [num(R, 9)])
    caller = Player(101, "Caller", [num(B, 3)])
    game = Game(
        game_id="g",
        players=[target, caller],
        deck=__import__("app.engine.deck", fromlist=["Deck"]).Deck(
            [num(R, 1), num(B, 2)],
            [num(R, 2)],
            rng=random.Random(0),
        ),
        config=GameConfig(),
        rng=random.Random(0),
        status=GameStatus.ACTIVE,
        current_index=0,
        active_color=CardColor.RED,
    )
    game.uno_vulnerable[100] = 1
    game.uno_declarations[100] = False

    events = game.catch_uno(101, 100)

    assert [event.type.value for event in events] == [
        "uno_penalty_applied",
        "uno_caught",
    ]
    assert 100 not in game.uno_vulnerable
    assert len(target.hand) == 3
