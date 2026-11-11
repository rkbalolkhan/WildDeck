import random
from collections import Counter

import pytest

from app.engine import (
    DECK_SIZE,
    CardColor,
    CardType,
    Deck,
    DeckEmptyError,
    InvalidDrawError,
    build_standard_cards,
)
from tests.engine_helpers import filler


def test_108_unique_cards() -> None:
    cards = build_standard_cards()
    assert len(cards) == DECK_SIZE == 108
    assert len({c.id for c in cards}) == 108


def test_distribution() -> None:
    counts = Counter((c.color, c.type, c.value) for c in build_standard_cards())
    for color in (CardColor.RED, CardColor.BLUE, CardColor.GREEN, CardColor.YELLOW):
        assert counts[(color, CardType.NUMBER, 0)] == 1
        for v in range(1, 10):
            assert counts[(color, CardType.NUMBER, v)] == 2
        for t in (CardType.SKIP, CardType.REVERSE, CardType.DRAW_TWO):
            assert counts[(color, t, None)] == 2
    assert counts[(CardColor.WILD, CardType.WILD, None)] == 4
    assert counts[(CardColor.WILD, CardType.WILD_DRAW_FOUR, None)] == 4


def test_shuffle_is_seeded_and_changes_order() -> None:
    a = [c.id for c in Deck.standard(random.Random(1)).draw_pile]
    b = [c.id for c in Deck.standard(random.Random(1)).draw_pile]
    c = [c.id for c in Deck.standard(random.Random(2)).draw_pile]
    assert a == b and a != c and a != [x.id for x in build_standard_cards()]
    assert sorted(a) == sorted(x.id for x in build_standard_cards())


def test_draw_one_and_many() -> None:
    d = Deck.standard(random.Random(0))
    assert len(d.draw()) == 1 and len(d.draw(5)) == 5 and d.draw_size == 102


@pytest.mark.parametrize("n", [0, -3])
def test_invalid_draw_count(n: int) -> None:
    with pytest.raises(InvalidDrawError):
        Deck(filler(3)).draw(n)


def test_overdraw_raises_without_mutation() -> None:
    d = Deck(filler(3))
    with pytest.raises(DeckEmptyError):
        d.draw(4)
    assert d.draw_size == 3


def test_recycles_discards_but_keeps_top() -> None:
    discards = filler(6)
    d = Deck([], discards, rng=random.Random(0))
    top = discards[-1]
    drawn = d.draw(5)
    assert d.top_discard == top and d.discard_size == 1
    assert {c.id for c in drawn} == {c.id for c in discards[:5]}


def test_no_recyclable_cards() -> None:
    d = Deck([], filler(1))
    with pytest.raises(DeckEmptyError):
        d.draw()
    assert d.draw_up_to(3) == [] and d.discard_size == 1


def test_draw_up_to_partial() -> None:
    assert len(Deck(filler(2)).draw_up_to(5)) == 2


def test_deck_round_trip() -> None:
    d = Deck(filler(4), filler(3))
    assert Deck.from_dict(d.to_dict()).to_dict() == d.to_dict()
