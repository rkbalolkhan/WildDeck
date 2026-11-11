"""Structured engine events. Pure data: no Telegram text or formatting."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(Enum):
    CARD_PLAYED = "card_played"
    CARD_DRAWN = "card_drawn"
    TURN_CHANGED = "turn_changed"
    DIRECTION_CHANGED = "direction_changed"
    PLAYER_SKIPPED = "player_skipped"
    COLOR_CHANGED = "color_changed"
    GAME_FINISHED = "game_finished"
    UNO_DECLARED = "uno_declared"
    UNO_MISSED = "uno_missed"
    UNO_CAUGHT = "uno_caught"
    UNO_PENALTY_APPLIED = "uno_penalty_applied"
    PENALTY_STACKED = "penalty_stacked"
    PENALTY_ACCEPTED = "penalty_accepted"
    PENALTY_RESOLVED = "penalty_resolved"
    WILD_DRAW_FOUR_CHALLENGED = "wild_draw_four_challenged"
    WILD_DRAW_FOUR_CHALLENGE_SUCCEEDED = "wild_draw_four_challenge_succeeded"
    WILD_DRAW_FOUR_CHALLENGE_FAILED = "wild_draw_four_challenge_failed"
    ROUND_FINISHED = "round_finished"
    SCORE_UPDATED = "score_updated"
    MATCH_FINISHED = "match_finished"


@dataclass(frozen=True, slots=True)
class GameEvent:
    """An event with JSON-compatible ``data``. Drawn card identities are never included."""

    type: EventType
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type.value, "data": dict(self.data)}
