import pytest

from app.engine import InvalidCardError, InvalidPlayerError, Player
from tests.engine_helpers import B, R, num, wd4, wild


def test_add_remove_and_sizes() -> None:
    p, c = Player(1, "A"), num(R, 3)
    p.add_card(c)
    assert p.hand_size == 1 and p.has_card(c.id)
    assert p.remove_card(c.id) == c and p.hand_size == 0


def test_cannot_add_same_card_twice_or_remove_missing() -> None:
    p, c = Player(1, "A"), num(R, 3)
    p.add_card(c)
    with pytest.raises(InvalidCardError):
        p.add_card(c)
    with pytest.raises(InvalidCardError):
        p.remove_card("nope")


@pytest.mark.parametrize("uid,name", [("x", "A"), (True, "A"), (1, " ")])
def test_invalid_identity(uid: object, name: str) -> None:
    with pytest.raises(InvalidPlayerError):
        Player(uid, name)  # type: ignore[arg-type]


def test_playable_cards() -> None:
    top = num(R, 5)
    hand = [num(R, 1), num(B, 5), num(B, 2), wild()]
    p = Player(1, "A", hand)
    assert {c.id for c in p.playable_cards(top, R)} == {hand[0].id, hand[1].id, hand[3].id}


def test_serialization() -> None:
    p = Player(1, "A", [num(R, 1), wd4()])
    assert Player.from_dict(p.to_dict()).to_dict() == p.to_dict()
