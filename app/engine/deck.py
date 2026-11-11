"""Standard 108-card deck, draw pile, discard pile and recycling."""

from __future__ import annotations

import random
from collections.abc import Iterable
from typing import Any

from app.engine.card import CHOOSABLE_COLORS, Card, CardColor, CardType
from app.engine.errors import DeckEmptyError, InvalidDrawError

DECK_SIZE = 108


def build_standard_cards() -> list[Card]:
    """Return the 108 standard cards in a fixed order with ids ``c000``..``c107``."""
    specs: list[tuple[CardColor, CardType, int | None]] = []
    for color in CHOOSABLE_COLORS:
        specs.append((color, CardType.NUMBER, 0))
        for value in range(1, 10):
            specs.extend([(color, CardType.NUMBER, value)] * 2)
        for action in (CardType.SKIP, CardType.REVERSE, CardType.DRAW_TWO):
            specs.extend([(color, action, None)] * 2)
    specs.extend([(CardColor.WILD, CardType.WILD, None)] * 4)
    specs.extend([(CardColor.WILD, CardType.WILD_DRAW_FOUR, None)] * 4)
    return [Card(f"c{i:03d}", c, t, v) for i, (c, t, v) in enumerate(specs)]


class Deck:
    """Draw pile plus discard pile. The *end* of each list is its top."""

    def __init__(
        self,
        draw_pile: Iterable[Card] = (),
        discard_pile: Iterable[Card] = (),
        rng: random.Random | None = None,
    ) -> None:
        self.draw_pile: list[Card] = list(draw_pile)
        self.discard_pile: list[Card] = list(discard_pile)
        self.rng = rng or random.Random()

    @classmethod
    def standard(cls, rng: random.Random | None = None, *, shuffle: bool = True) -> Deck:
        deck = cls(build_standard_cards(), rng=rng)
        if shuffle:
            deck.shuffle()
        return deck

    @property
    def draw_size(self) -> int:
        return len(self.draw_pile)

    @property
    def discard_size(self) -> int:
        return len(self.discard_pile)

    @property
    def top_discard(self) -> Card | None:
        return self.discard_pile[-1] if self.discard_pile else None

    @property
    def available(self) -> int:
        """Cards drawable right now, counting what recycling would release."""
        return self.draw_size + max(0, self.discard_size - 1)

    def shuffle(self) -> None:
        self.rng.shuffle(self.draw_pile)

    def draw(self, count: int = 1) -> list[Card]:
        """Draw exactly ``count`` cards or raise without changing anything."""
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise InvalidDrawError(f"Must draw at least one card, got {count!r}")
        if count > self.available:
            raise DeckEmptyError(f"Cannot draw {count} cards; only {self.available} available")
        drawn: list[Card] = []
        for _ in range(count):
            if not self.draw_pile:
                self._recycle()
            drawn.append(self.draw_pile.pop())
        return drawn

    def draw_up_to(self, count: int) -> list[Card]:
        """Draw as many as possible (for penalties); may return fewer, even none."""
        if count < 1:
            raise InvalidDrawError(f"Must draw at least one card, got {count!r}")
        n = min(count, self.available)
        return self.draw(n) if n else []

    def discard(self, card: Card) -> None:
        self.discard_pile.append(card)

    def return_to_draw_pile(self, card: Card) -> None:
        """Put a card back into the draw pile and reshuffle it."""
        self.draw_pile.append(card)
        self.shuffle()

    def _recycle(self) -> None:
        """Keep the top discard; shuffle the rest into a new draw pile."""
        if self.discard_size < 2:
            raise DeckEmptyError("Draw pile empty and no discarded cards to recycle")
        top = self.discard_pile.pop()
        self.draw_pile, self.discard_pile = self.discard_pile, [top]
        self.shuffle()

    def to_dict(self) -> dict[str, Any]:
        return {
            "draw_pile": [c.to_dict() for c in self.draw_pile],
            "discard_pile": [c.to_dict() for c in self.discard_pile],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], rng: random.Random | None = None) -> Deck:
        return cls(
            [Card.from_dict(c) for c in data["draw_pile"]],
            [Card.from_dict(c) for c in data["discard_pile"]],
            rng=rng,
        )
