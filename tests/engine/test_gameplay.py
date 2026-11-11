import pytest

from app.engine import (
    CardColor,
    EventType,
    GameStatus,
    IllegalMoveError,
    InvalidCardError,
    InvalidColorError,
    InvalidGameStateError,
    InvalidPlayerError,
    InvalidTurnError,
)
from tests.engine_helpers import B, G, R, Y, draw_two, make_game, num, wd4, wild


def test_play_number() -> None:
    c = num(R, 7)
    g = make_game([[c, num(B, 1)], [num(B, 2)]], num(R, 5))
    g.play_card(100, c.id)
    assert g.top_card == c and g.hand_sizes[100] == 1 and g.current_player_id == 101


def test_play_changes_active_color() -> None:
    c = num(B, 5)
    g = make_game([[c, num(B, 1)], [num(B, 2)]], num(R, 5))
    g.play_card(100, c.id)
    assert g.active_color is B
    assert any(e.type is EventType.COLOR_CHANGED for e in g.events)


def test_play_wild_requires_valid_color() -> None:
    w = wild()
    g = make_game([[w, num(B, 1)], [num(B, 2)]], num(R, 5))
    for bad in (None, CardColor.WILD, "purple"):
        with pytest.raises(InvalidColorError):
            g.play_card(100, w.id, bad)
    g.play_card(100, w.id, "green")
    assert g.active_color is G and g.current_player_id == 101


def test_chosen_color_rejected_for_non_wild() -> None:
    c = num(R, 7)
    g = make_game([[c, num(B, 1)], [num(B, 2)]], num(R, 5))
    with pytest.raises(InvalidColorError):
        g.play_card(100, c.id, R)


def test_wild_draw_four_effect() -> None:
    w = wd4()
    g = make_game([[w, num(B, 1)], [num(B, 2)], [num(B, 3)]], num(R, 5))
    g.play_card(100, w.id, Y)
    assert g.hand_sizes[101] == 5 and g.current_index == 2 and g.active_color is Y


def test_draw_unplayable_ends_turn() -> None:
    g = make_game([[num(B, 1)], [num(B, 2)]], num(R, 5), draw_pile=[num(G, 9)])
    res = g.draw_card(100)
    assert res.card is not None and not res.can_play
    assert g.hand_sizes[100] == 2 and g.current_player_id == 101


def test_draw_playable_then_play_only_that_card() -> None:
    drawn, other = num(R, 8), num(R, 1)
    g = make_game([[other], [num(B, 2)]], num(R, 5), draw_pile=[drawn])
    res = g.draw_card(100)
    assert res.can_play and g.current_player_id == 100
    assert [c.id for c in g.get_playable_cards(100)] == [drawn.id]
    with pytest.raises(IllegalMoveError):
        g.play_card(100, other.id)
    with pytest.raises(IllegalMoveError):
        g.draw_card(100)
    g.play_card(100, drawn.id)
    assert g.current_player_id == 101 and g.drawn_card_id is None


def test_pass_after_playable_draw() -> None:
    g = make_game([[num(B, 1)], [num(B, 2)]], num(R, 5), draw_pile=[num(R, 8)])
    g.draw_card(100)
    g.pass_turn(100)
    assert g.current_player_id == 101
    with pytest.raises(IllegalMoveError):
        g.pass_turn(101)


def test_draw_from_empty_everything_passes_turn() -> None:
    g = make_game([[num(B, 1)], [num(B, 2)]], num(R, 5), draw_pile=[])
    res = g.draw_card(100)
    assert res.card is None and g.current_player_id == 101


def test_draw_recycles_discards() -> None:
    g = make_game([[num(B, 1)], [num(B, 2)]], num(R, 5), draw_pile=[])
    g.deck.discard_pile = [num(G, 1), num(G, 2), num(R, 5)]
    g.draw_card(100)
    assert g.hand_sizes[100] == 2 and g.top_card.value == 5
    g.validate_integrity(expected_total=None)


def test_win_and_actions_afterwards_blocked() -> None:
    last = num(R, 9)
    g = make_game([[last], [num(B, 2)]], num(R, 5))
    g.play_card(100, last.id)
    assert g.status is GameStatus.FINISHED and g.winner_id == 100
    assert any(e.type is EventType.GAME_FINISHED for e in g.events)
    for call in (lambda: g.draw_card(101), lambda: g.play_card(101, "x"), lambda: g.pass_turn(101)):
        with pytest.raises(InvalidGameStateError):
            call()


def test_winning_draw_two_still_penalises() -> None:
    last = draw_two(R)
    g = make_game([[last], [num(B, 2)]], num(R, 5))
    g.play_card(100, last.id)
    assert g.winner_id == 100 and g.hand_sizes[101] == 3


def test_cancel_transitions() -> None:
    g = make_game([[num(R, 1)], [num(R, 2)]], num(R, 5))
    g.cancel()
    assert g.status is GameStatus.CANCELLED
    with pytest.raises(InvalidGameStateError):
        g.transition_to(GameStatus.ACTIVE)


def test_events_hide_drawn_card_identity() -> None:
    g = make_game([[num(B, 1)], [num(B, 2)]], num(R, 5), draw_pile=[num(G, 9)])
    g.draw_card(100)
    drawn = [e for e in g.events if e.type is EventType.CARD_DRAWN][0]
    assert set(drawn.data) == {"player_id", "count", "reason"}


def test_public_state_has_no_hands() -> None:
    g = make_game([[num(R, 1)], [num(R, 2)]], num(R, 5))
    assert "hand" not in str(g.public_state()).replace("hand_size", "")


def failing_calls(g, c_other, c_bad):
    return [
        lambda: g.play_card(999, c_bad.id),
        lambda: g.play_card(101, c_other.id),
        lambda: g.play_card(100, "missing"),
        lambda: g.play_card(100, c_bad.id),
        lambda: g.play_card(100, c_bad.id, "red"),
        lambda: g.draw_card(101),
        lambda: g.draw_card(999),
        lambda: g.pass_turn(100),
    ]


def test_failed_actions_do_not_mutate_state() -> None:
    c_bad, c_other = num(B, 9), num(B, 2)
    g = make_game([[c_bad, num(B, 1)], [c_other]], num(R, 5))
    before = g.to_dict()
    errors = (
        InvalidPlayerError,
        InvalidTurnError,
        InvalidCardError,
        IllegalMoveError,
        InvalidColorError,
    )
    for call in failing_calls(g, c_other, c_bad):
        with pytest.raises(errors):
            call()
        assert g.to_dict() == before
    assert g.events == []


def test_failed_wild_color_does_not_mutate() -> None:
    w = wild()
    g = make_game([[w, num(B, 1)], [num(B, 2)]], num(R, 5))
    before = g.to_dict()
    with pytest.raises(InvalidColorError):
        g.play_card(100, w.id)
    assert g.to_dict() == before
