"""Player model and hand management. No Telegram dependency."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.engine import rules
from app.engine.card import Card, CardColor
from app.engine.errors import InvalidCardError, InvalidPlayerError


@dataclass(eq=False)
class Player:
    user_id: int
    name: str
    hand: list[Card] = field(default_factory=list)
    is_active: bool = True

    def __post_init__(self) -> None:
        if isinstance(self.user_id, bool) or not isinstance(self.user_id, int):
            raise InvalidPlayerError(f"user_id must be an int, got {self.user_id!r}")
        if not isinstance(self.name, str) or not self.name.strip():
            raise InvalidPlayerError("Player name must be a non-empty string")
        if len({c.id for c in self.hand}) != len(self.hand):
            raise InvalidPlayerError("Hand contains duplicate cards")

    @property
    def hand_size(self) -> int:
        return len(self.hand)

    def has_card(self, card_id: str) -> bool:
        return any(c.id == card_id for c in self.hand)

    def get_card(self, card_id: str) -> Card:
        for card in self.hand:
            if card.id == card_id:
                return card
        raise InvalidCardError(f"Player {self.user_id} does not hold card {card_id!r}")

    def add_card(self, card: Card) -> None:
        if self.has_card(card.id):
            raise InvalidCardError(f"Card {card.id!r} is already in the hand")
        self.hand.append(card)

    def add_cards(self, cards: list[Card]) -> None:
        for card in cards:
            self.add_card(card)

    def remove_card(self, card_id: str) -> Card:
        card = self.get_card(card_id)
        self.hand.remove(card)
        return card

    def playable_cards(self, top_card: Card, active_color: CardColor) -> list[Card]:
        """Cards matching the discard state (ignores turn order and the post-draw limit)."""
        return [
            c for c in self.hand if rules.is_card_playable(c, self.hand, top_card, active_color)
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "hand": [c.to_dict() for c in self.hand],
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Player:
        return cls(
            user_id=data["user_id"],
            name=data["name"],
            hand=[Card.from_dict(c) for c in data["hand"]],
            is_active=data["is_active"],
        )
