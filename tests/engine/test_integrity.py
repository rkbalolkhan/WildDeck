import json
import random

import pytest

from app.engine import Game, GameStatus, InvalidGameStateError, InvalidPlayerError, Player
from tests.engine_helpers import R, make_game, num


def play_some(seed: int, steps: int = 40) -> Game:
    rng = random.Random(seed)
    g = Game.new([Player(i, f"P{i}") for i in range(1, 5)], rng=random.Random(seed))
    for _ in range(steps):
        if g.status is not GameStatus.ACTIVE:
            break
        pid = g.current_player_id
        playable = g.get_playable_cards(pid)
        if playable:
            c = rng.choice(playable)
            g.play_card(pid, c.id, "red" if c.is_wild else None)
        else:
            g.draw_card(pid)
    return g


@pytest.mark.parametrize("seed", range(10))
def test_round_trip(seed: int) -> None:
    g = play_some(seed)
    data = json.loads(json.dumps(g.to_dict()))  # JSON-compatible
    g2 = Game.from_dict(data)
    assert g2.to_dict() == g.to_dict()
    assert g2.player_ids == g.player_ids and g2.direction is g.direction
    assert g2.active_color is g.active_color and g2.winner_id == g.winner_id
    g2.validate_integrity()


def test_round_trip_preserves_winner_and_drawn_card() -> None:
    last = num(R, 9)
    g = make_game([[last], [num(R, 2)]], num(R, 5))
    g.play_card(100, last.id)
    assert Game.from_dict(g.to_dict()).winner_id == 100
    g2 = make_game([[num(R, 1)], [num(R, 2)]], num(R, 5), draw_pile=[num(R, 8)])
    g2.draw_card(100)
    assert Game.from_dict(g2.to_dict()).drawn_card_id == g2.drawn_card_id


def test_deserialized_game_is_playable() -> None:
    g = Game.from_dict(play_some(3).to_dict())
    pid = g.current_player_id
    if g.status is GameStatus.ACTIVE:
        g.pass_turn(pid) if g.drawn_card_id else g.draw_card(pid)
        g.validate_integrity()


def test_duplicate_card_detected() -> None:
    c = num(R, 1)
    g = make_game([[c], [c]], num(R, 5))
    with pytest.raises(InvalidGameStateError):
        g.validate_integrity(expected_total=None)
    with pytest.raises(InvalidGameStateError):
        Game.from_dict(g.to_dict())


def test_bad_serialized_data() -> None:
    data = play_some(1).to_dict()
    with pytest.raises(InvalidGameStateError):
        Game.from_dict({k: v for k, v in data.items() if k != "status"})
    data["players"].append(dict(data["players"][0], hand=[]))
    with pytest.raises(InvalidPlayerError):
        Game.from_dict(data)


def test_card_conservation_through_play() -> None:
    g = play_some(11, steps=80)
    g.validate_integrity()
    assert len(g.all_cards()) == 108
