import random

import pytest

from app.engine import (
    CHOOSABLE_COLORS,
    DECK_SIZE,
    CardColor,
    CardType,
    Direction,
    EventType,
    Game,
    GameStatus,
    InvalidPlayerError,
    Player,
    build_standard_cards,
)
from tests.engine_helpers import rigged_deck


def roster(n: int) -> list[Player]:
    return [Player(10 + i, f"P{i}") for i in range(n)]


@pytest.mark.parametrize("n", [2, 5, 10])
def test_valid_player_counts(n: int) -> None:
    g = Game.new(roster(n), rng=random.Random(n))
    assert g.status is GameStatus.ACTIVE
    g.validate_integrity()
    assert g.discard_pile_size == 1


@pytest.mark.parametrize("n", [0, 1, 11])
def test_invalid_player_counts(n: int) -> None:
    with pytest.raises(InvalidPlayerError):
        Game.new(roster(n))


def test_duplicate_players_rejected() -> None:
    with pytest.raises(InvalidPlayerError):
        Game.new([Player(1, "A"), Player(1, "B")])


def test_non_empty_hand_rejected() -> None:
    p = Player(1, "A", [build_standard_cards()[0]])
    with pytest.raises(InvalidPlayerError):
        Game.new([p, Player(2, "B")])


def test_seven_cards_each_and_conservation() -> None:
    g = Game.new(roster(4), rng=random.Random(3))
    start_sizes = g.hand_sizes
    assert all(s >= 7 for s in start_sizes.values()) and sum(start_sizes.values()) <= 30
    assert len(g.all_cards()) == DECK_SIZE


@pytest.mark.parametrize("seed", range(150))
def test_initial_card_never_wd4_and_color_valid(seed: int) -> None:
    g = Game.new(roster(3), rng=random.Random(seed))
    assert g.top_card.type is not CardType.WILD_DRAW_FOUR
    assert g.active_color in CHOOSABLE_COLORS
    if not g.top_card.is_wild:
        assert g.active_color is g.top_card.color


def find(pred) -> object:
    return next(c for c in build_standard_cards() if pred(c))


def start_with(target, n: int = 3) -> Game:
    rng = random.Random(5)
    return Game.new(roster(n), rng=rng, deck=rigged_deck(n, target, rng))


def test_start_number() -> None:
    t = find(lambda c: c.type is CardType.NUMBER and c.color is CardColor.GREEN)
    g = start_with(t)
    assert g.top_card == t and g.current_index == 0 and g.active_color is CardColor.GREEN
    assert g.hand_sizes == {10: 7, 11: 7, 12: 7}


def test_start_skip() -> None:
    g = start_with(find(lambda c: c.type is CardType.SKIP))
    assert g.current_index == 1
    assert any(e.type is EventType.PLAYER_SKIPPED for e in g.events)


@pytest.mark.parametrize("n,expected", [(3, 2), (2, 1)])
def test_start_reverse(n: int, expected: int) -> None:
    g = start_with(find(lambda c: c.type is CardType.REVERSE), n)
    assert g.direction is Direction.COUNTERCLOCKWISE and g.current_index == expected


def test_start_draw_two() -> None:
    g = start_with(find(lambda c: c.type is CardType.DRAW_TWO))
    assert g.hand_sizes[10] == 9 and g.current_index == 1


def test_start_wild_random_color() -> None:
    g = start_with(find(lambda c: c.type is CardType.WILD))
    assert g.top_card.type is CardType.WILD and g.active_color in CHOOSABLE_COLORS
    assert g.current_index == 0


def test_start_wild_draw_four_is_reshuffled() -> None:
    t = find(lambda c: c.type is CardType.WILD_DRAW_FOUR)
    g = start_with(t)
    assert g.top_card.type is not CardType.WILD_DRAW_FOUR
    assert t.id in {c.id for c in g.deck.draw_pile}
    g.validate_integrity()
