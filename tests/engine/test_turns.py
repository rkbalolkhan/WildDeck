from app.engine import Direction, EventType
from tests.engine_helpers import B, R, draw_two, make_game, num, reverse, skip

CW, CCW = Direction.CLOCKWISE, Direction.COUNTERCLOCKWISE


def three(card, *, current=0, direction=CW, top=None):
    hands = [[num(B, 1)], [num(B, 2)], [num(B, 3)]]
    hands[current].append(card)
    return make_game(
        hands,
        top or num(R, 5),
        current=current,
        direction=direction,
    )


def test_clockwise_and_wraparound() -> None:
    c = num(R, 1)
    g = three(c, current=2)
    g.play_card(102, c.id)
    assert g.current_index == 0


def test_counterclockwise() -> None:
    c = num(R, 1)
    g = three(c, direction=CCW)
    g.play_card(100, c.id)
    assert g.current_index == 2


def test_skip_cw_and_ccw() -> None:
    c = skip(R)
    g = three(c)
    g.play_card(100, c.id)
    assert g.current_index == 2
    c2 = skip(R)
    g2 = three(c2, direction=CCW)
    g2.play_card(100, c2.id)
    assert g2.current_index == 1
    assert any(e.type is EventType.PLAYER_SKIPPED for e in g.events)


def test_reverse_three_players() -> None:
    c = reverse(R)
    g = three(c)
    g.play_card(100, c.id)
    assert g.direction is CCW and g.current_index == 2


def test_reverse_two_players_acts_like_skip() -> None:
    c = reverse(R)
    g = make_game([[c, num(B, 1)], [num(B, 2)]], num(R, 5))
    g.play_card(100, c.id)
    assert g.direction is CCW and g.current_index == 0


def test_skip_two_players_same_player_again() -> None:
    c = skip(R)
    g = make_game([[c, num(B, 1)], [num(B, 2)]], num(R, 5))
    g.play_card(100, c.id)
    assert g.current_index == 0


def test_draw_two_skips_victim() -> None:
    c = draw_two(R)
    g = three(c)
    g.play_card(100, c.id)
    assert g.hand_sizes[101] == 3 and g.current_index == 2


def test_turn_changed_event() -> None:
    c = num(R, 1)
    g = three(c)
    g.play_card(100, c.id)
    ev = [e for e in g.events if e.type is EventType.TURN_CHANGED][0]
    assert ev.data == {"player_id": 101, "previous_player_id": 100}
