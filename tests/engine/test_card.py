import pytest

from app.engine import Card, CardColor, CardType, InvalidCardError


@pytest.mark.parametrize("value", range(10))
def test_valid_number_cards(value: int) -> None:
    c = Card("a", CardColor.RED, CardType.NUMBER, value)
    assert c.value == value and not c.is_wild and not c.is_action


@pytest.mark.parametrize("t", [CardType.SKIP, CardType.REVERSE, CardType.DRAW_TWO])
def test_valid_action_cards(t: CardType) -> None:
    assert Card("a", CardColor.BLUE, t).is_action


@pytest.mark.parametrize("t", [CardType.WILD, CardType.WILD_DRAW_FOUR])
def test_valid_wild_cards(t: CardType) -> None:
    assert Card("a", CardColor.WILD, t).is_wild


@pytest.mark.parametrize(
    "args",
    [
        (CardColor.RED, CardType.NUMBER, 10),
        (CardColor.RED, CardType.NUMBER, -1),
        (CardColor.RED, CardType.NUMBER, None),
        (CardColor.RED, CardType.NUMBER, True),
        (CardColor.WILD, CardType.NUMBER, 3),
        (CardColor.RED, CardType.SKIP, 1),
        (CardColor.WILD, CardType.REVERSE, None),
        (CardColor.WILD, CardType.DRAW_TWO, None),
        (CardColor.RED, CardType.WILD, None),
        (CardColor.GREEN, CardType.WILD_DRAW_FOUR, None),
        (CardColor.WILD, CardType.WILD, 4),
    ],
)
def test_invalid_combinations(args: tuple) -> None:
    with pytest.raises(InvalidCardError):
        Card("a", *args)


def test_invalid_id_and_enums() -> None:
    with pytest.raises(InvalidCardError):
        Card("", CardColor.RED, CardType.SKIP)
    with pytest.raises(InvalidCardError):
        Card("a", "red", CardType.SKIP)  # type: ignore[arg-type]


def test_identical_cards_stay_distinct() -> None:
    a = Card("a", CardColor.RED, CardType.NUMBER, 5)
    b = Card("b", CardColor.RED, CardType.NUMBER, 5)
    assert a != b and len({a, b}) == 2


def test_round_trip_and_bad_data() -> None:
    c = Card("a", CardColor.YELLOW, CardType.NUMBER, 7)
    assert Card.from_dict(c.to_dict()) == c
    with pytest.raises(InvalidCardError):
        Card.from_dict({"id": "a", "color": "pink", "type": "number", "value": 1})
    with pytest.raises(InvalidCardError):
        Card.from_dict({})
