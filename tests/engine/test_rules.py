import pytest

from app.engine import IllegalMoveError, rules
from tests.engine_helpers import (
    B,
    G,
    R,
    Y,
    draw_two,
    make_game,
    num,
    reverse,
    skip,
    wd4,
    wild,
)


def test_color_number_action_wild_matches() -> None:
    top = num(R, 5)
    ok = [num(R, 9), num(B, 5), wild()]
    bad = [num(B, 9), skip(B)]
    g = make_game([ok + bad], top)
    p = g.players[0]
    assert {c.id for c in g.get_playable_cards(100)} == {c.id for c in ok}
    assert all(not rules.is_playable(c, g, p) for c in bad)


def test_action_type_matches_across_colors() -> None:
    g = make_game([[skip(B), reverse(B), draw_two(B)]], skip(R))
    assert [c.type.value for c in g.get_playable_cards(100)] == ["skip"]


def test_active_color_overrides_wild_printed_color() -> None:
    g = make_game([[num(G, 1), num(R, 1)]], wild(), active_color=G)
    assert [c.color for c in g.get_playable_cards(100)] == [G]


def test_wd4_only_without_active_color_card() -> None:
    w = wd4()
    legal = make_game([[w, num(B, 1), skip(Y)]], num(R, 5))
    assert w.id in {c.id for c in legal.get_playable_cards(100)}
    illegal = make_game([[w, num(R, 1)]], num(R, 5))
    assert w.id not in {c.id for c in illegal.get_playable_cards(100)}
    with pytest.raises(IllegalMoveError, match="Wild Draw Four"):
        illegal.play_card(100, w.id, "blue")


def test_wild_in_hand_does_not_block_wd4() -> None:
    w = wd4()
    g = make_game([[w, wild()]], num(R, 5))
    assert w.id in {c.id for c in g.get_playable_cards(100)}


def test_invalid_move_message() -> None:
    c = num(B, 9)
    g = make_game([[c]], num(R, 5))
    with pytest.raises(IllegalMoveError):
        g.play_card(100, c.id)
