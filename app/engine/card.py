"""Card colors, types and the immutable :class:`Card` model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.engine.errors import InvalidCardError


class CardColor(Enum):
    RED = "red"
    BLUE = "blue"
    GREEN = "green"
    YELLOW = "yellow"
    WILD = "wild"


class CardType(Enum):
    NUMBER = "number"
    SKIP = "skip"
    REVERSE = "reverse"
    DRAW_TWO = "draw_two"
    WILD = "wild"
    WILD_DRAW_FOUR = "wild_draw_four"


#: Colors that can be printed on a card or chosen for a wild card.
CHOOSABLE_COLORS: tuple[CardColor, ...] = (
    CardColor.RED,
    CardColor.BLUE,
    CardColor.GREEN,
    CardColor.YELLOW,
)
ACTION_TYPES = frozenset({CardType.SKIP, CardType.REVERSE, CardType.DRAW_TWO})
WILD_TYPES = frozenset({CardType.WILD, CardType.WILD_DRAW_FOUR})
MIN_NUMBER, MAX_NUMBER = 0, 9


@dataclass(frozen=True, slots=True)
class Card:
    """A single physical card. ``id`` makes identical-looking cards distinct."""

    id: str
    color: CardColor
    type: CardType
    value: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise InvalidCardError("Card id must be a non-empty string")
        if not isinstance(self.color, CardColor):
            raise InvalidCardError(f"Invalid card color: {self.color!r}")
        if not isinstance(self.type, CardType):
            raise InvalidCardError(f"Invalid card type: {self.type!r}")

        if self.type is CardType.NUMBER:
            if self.color is CardColor.WILD:
                raise InvalidCardError("Number cards cannot be wild-colored")
            ok = isinstance(self.value, int) and not isinstance(self.value, bool)
            if not ok or not MIN_NUMBER <= self.value <= MAX_NUMBER:  # type: ignore[operator]
                raise InvalidCardError(
                    f"Number cards need a value {MIN_NUMBER}-{MAX_NUMBER}, got {self.value!r}"
                )
        elif self.type in ACTION_TYPES:
            if self.color is CardColor.WILD:
                raise InvalidCardError(f"{self.type.value} cards need a real color")
            if self.value is not None:
                raise InvalidCardError(f"{self.type.value} cards cannot have a number value")
        else:  # wild / wild draw four
            if self.color is not CardColor.WILD:
                raise InvalidCardError(f"{self.type.value} cards must use the WILD color")
            if self.value is not None:
                raise InvalidCardError(f"{self.type.value} cards cannot have a number value")

    @property
    def is_wild(self) -> bool:
        return self.type in WILD_TYPES

    @property
    def is_action(self) -> bool:
        return self.type in ACTION_TYPES

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "color": self.color.value,
            "type": self.type.value,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Card:
        try:
            return cls(
                id=data["id"],
                color=CardColor(data["color"]),
                type=CardType(data["type"]),
                value=data.get("value"),
            )
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            raise InvalidCardError(f"Cannot deserialize card from {data!r}") from exc
