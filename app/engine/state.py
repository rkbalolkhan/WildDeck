"""Game status, direction and configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.engine import rules
from app.engine.deck import DECK_SIZE
from app.engine.errors import GameError


class GameStatus(Enum):
    WAITING = "waiting"
    ACTIVE = "active"
    FINISHED = "finished"
    CANCELLED = "cancelled"


ALLOWED_TRANSITIONS: dict[GameStatus, frozenset[GameStatus]] = {
    GameStatus.WAITING: frozenset({GameStatus.ACTIVE, GameStatus.CANCELLED}),
    GameStatus.ACTIVE: frozenset({GameStatus.FINISHED, GameStatus.CANCELLED}),
    GameStatus.FINISHED: frozenset(),
    GameStatus.CANCELLED: frozenset(),
}


class Direction(Enum):
    CLOCKWISE = 1
    COUNTERCLOCKWISE = -1

    def reversed(self) -> Direction:
        return Direction(-self.value)


@dataclass(frozen=True, slots=True)
class GameRules:
    stacking_enabled: bool = False
    stack_draw_two: bool = True
    stack_wild_draw_four: bool = True
    allow_mixed_stacking: bool = False
    uno_penalty_enabled: bool = True
    uno_penalty_cards: int = 2
    auto_uno: bool = False
    wild_draw_four_challenge: bool = False
    scoring_enabled: bool = True
    match_target_score: int = 500

    def __post_init__(self) -> None:
        if self.uno_penalty_cards < 0:
            raise GameError("uno_penalty_cards must be non-negative")
        if self.match_target_score < 0:
            raise GameError("match_target_score must be non-negative")
        if not self.stacking_enabled:
            object.__setattr__(self, "stack_draw_two", False)
            object.__setattr__(self, "stack_wild_draw_four", False)
            object.__setattr__(self, "allow_mixed_stacking", False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stacking_enabled": self.stacking_enabled,
            "stack_draw_two": self.stack_draw_two,
            "stack_wild_draw_four": self.stack_wild_draw_four,
            "allow_mixed_stacking": self.allow_mixed_stacking,
            "uno_penalty_enabled": self.uno_penalty_enabled,
            "uno_penalty_cards": self.uno_penalty_cards,
            "auto_uno": self.auto_uno,
            "wild_draw_four_challenge": self.wild_draw_four_challenge,
            "scoring_enabled": self.scoring_enabled,
            "match_target_score": self.match_target_score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> GameRules:
        if not data:
            return cls()
        return cls(**data)


@dataclass(frozen=True, slots=True)
class GameConfig:
    min_players: int = rules.MIN_PLAYERS
    max_players: int = rules.MAX_PLAYERS
    initial_hand_size: int = rules.INITIAL_HAND_SIZE
    rules: GameRules = field(default_factory=GameRules)

    def __post_init__(self) -> None:
        if not 2 <= self.min_players <= self.max_players:
            raise GameError("Config needs 2 <= min_players <= max_players")
        if self.initial_hand_size < 1:
            raise GameError("initial_hand_size must be at least 1")
        if self.max_players * self.initial_hand_size + 2 > DECK_SIZE:
            raise GameError("Deck too small for max_players * initial_hand_size")
        object.__setattr__(
            self,
            "rules",
            GameRules.from_dict(
                self.rules.to_dict() if isinstance(self.rules, GameRules) else self.rules
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_players": self.min_players,
            "max_players": self.max_players,
            "initial_hand_size": self.initial_hand_size,
            "rules": self.rules.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GameConfig:
        payload = dict(data)
        payload["rules"] = GameRules.from_dict(payload.get("rules"))
        return cls(**payload)
