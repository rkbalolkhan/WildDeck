"""The :class:`Game` aggregate: state, initialization, read-only views, serialization."""

from __future__ import annotations

import random
import uuid
from collections import Counter
from collections.abc import Sequence
from typing import Any

from app.engine import actions, rules
from app.engine.actions import DrawResult
from app.engine.card import CHOOSABLE_COLORS, Card, CardColor, CardType
from app.engine.deck import DECK_SIZE, Deck
from app.engine.errors import (
    GameError,
    IllegalMoveError,
    InvalidGameStateError,
    InvalidPlayerError,
    InvalidTurnError,
)
from app.engine.events import EventType, GameEvent
from app.engine.player import Player
from app.engine.state import ALLOWED_TRANSITIONS, Direction, GameConfig, GameRules, GameStatus

__all__ = ["Direction", "Game", "GameConfig", "GameRules", "GameStatus", "Match"]


class Match:
    """Simple match tracker for cumulative scores across rounds."""

    def __init__(
        self,
        players: Sequence[Player],
        *,
        target_score: int = 500,
        round_scores: dict[int, int] | None = None,
    ) -> None:
        self.players = list(players)
        self.target_score = target_score
        self.scores = {
            p.user_id: int(round_scores.get(p.user_id, 0)) if round_scores else 0
            for p in self.players
        }
        self.round_number = 1
        self.finished = False
        self.winner_id: int | None = None

    def start_round(self) -> None:
        if self.finished:
            raise InvalidGameStateError("Match already finished")
        self.round_number += 1

    def record_round_result(self, game: Game) -> None:
        if game.winner_id is None:
            raise InvalidGameStateError("Round has no winner")
        winner_id = game.winner_id
        if not game.round_scores:
            return
        if winner_id in game.round_scores:
            self.scores[winner_id] += game.round_scores[winner_id]
            for pid, value in game.round_scores.items():
                if pid != winner_id:
                    self.scores.setdefault(pid, 0)
                    self.scores[pid] += value
        if any(score >= self.target_score for score in self.scores.values()):
            self.finished = True
            self.winner_id = max(self.scores, key=self.scores.get)
            if len({s for s in self.scores.values() if s >= self.target_score}) > 1:
                top = max(self.scores.values())
                leaders = [pid for pid, score in self.scores.items() if score == top]
                self.winner_id = leaders[0] if len(leaders) == 1 else None

    def is_finished(self) -> bool:
        return self.finished or any(score >= self.target_score for score in self.scores.values())

    def get_standings(self) -> list[tuple[int, int]]:
        return sorted(self.scores.items(), key=lambda item: (-item[1], item[0]))


class Game:
    """One UNO game. Construct with :meth:`new`; restore with :meth:`from_dict`."""

    def __init__(
        self,
        *,
        game_id: str,
        players: list[Player],
        deck: Deck,
        config: GameConfig,
        rng: random.Random,
        status: GameStatus = GameStatus.WAITING,
        current_index: int = 0,
        direction: Direction = Direction.CLOCKWISE,
        active_color: CardColor = CardColor.RED,
        winner_id: int | None = None,
        drawn_card_id: str | None = None,
        uno_declarations: dict[int, bool] | None = None,
        uno_vulnerable: dict[int, int] | None = None,
        pending_penalty: dict[str, Any] | None = None,
        pending_challenge: dict[str, Any] | None = None,
        round_scores: dict[int, int] | None = None,
        match_scores: dict[int, int] | None = None,
        round_winner_id: int | None = None,
        match_winner_id: int | None = None,
    ) -> None:
        self.game_id = game_id
        self.players = players
        self.deck = deck
        self.config = config
        self.rng = rng
        self.status = status
        self.current_index = current_index
        self.direction = direction
        self.active_color = active_color
        self.winner_id = winner_id
        self.drawn_card_id = drawn_card_id
        self.events: list[GameEvent] = []
        self.uno_declarations: dict[int, bool] = uno_declarations or {}
        self.uno_vulnerable: dict[int, int] = uno_vulnerable or {}
        self.pending_penalty: dict[str, Any] | None = pending_penalty
        self.pending_challenge: dict[str, Any] | None = pending_challenge
        self.round_scores: dict[int, int] = round_scores or {p.user_id: 0 for p in players}
        self.match_scores: dict[int, int] = match_scores or {p.user_id: 0 for p in players}
        self.round_winner_id: int | None = round_winner_id
        self.match_winner_id: int | None = match_winner_id
        self.match = Match(
            players,
            target_score=self.config.rules.match_target_score,
            round_scores=self.round_scores,
        )
        self._uno_window_player_id: int | None = None

    @classmethod
    def new(
        cls,
        players: Sequence[Player],
        *,
        game_id: str | None = None,
        config: GameConfig | None = None,
        rng: random.Random | None = None,
        deck: Deck | None = None,
    ) -> Game:
        """Validate, deal and start a game. ``players[0]`` sits left of the dealer.

        ``deck`` lets tests inject a rigged deck; it must hold all cards in its draw pile.
        """
        cfg = config or GameConfig()
        rng = rng or random.Random()
        roster = list(players)
        if not cfg.min_players <= len(roster) <= cfg.max_players:
            raise InvalidPlayerError(
                f"A game needs {cfg.min_players}-{cfg.max_players} players, got {len(roster)}"
            )
        if len({p.user_id for p in roster}) != len(roster):
            raise InvalidPlayerError("Duplicate players are not allowed")
        if any(p.hand for p in roster):
            raise InvalidPlayerError("Players must start with empty hands")

        game = cls(
            game_id=game_id or uuid.uuid4().hex,
            players=roster,
            deck=deck or Deck.standard(rng),
            config=cfg,
            rng=rng,
        )
        game.deck.rng = rng
        game._start()
        return game

    def _start(self) -> None:
        """Deal, flip the initial card, apply its starting effect, go ACTIVE."""
        for _ in range(self.config.initial_hand_size):
            for player in self.players:
                player.add_card(self.deck.draw(1)[0])

        while True:
            card = self.deck.draw(1)[0]
            if card.type is not CardType.WILD_DRAW_FOUR:
                break
            self.deck.return_to_draw_pile(card)
        self.deck.discard(card)

        n = len(self.players)
        self.current_index = 0
        if card.is_wild:
            self.active_color = self.rng.choice(CHOOSABLE_COLORS)
            self.events.append(
                GameEvent(EventType.COLOR_CHANGED, {"color": self.active_color.value})
            )
        else:
            self.active_color = card.color

        if card.type is CardType.SKIP:
            self.events.append(
                GameEvent(EventType.PLAYER_SKIPPED, {"player_id": self.player_ids[0]})
            )
            self.current_index = 1 % n
        elif card.type is CardType.REVERSE:
            self.direction = Direction.COUNTERCLOCKWISE
            self.events.append(
                GameEvent(EventType.DIRECTION_CHANGED, {"direction": self.direction.value})
            )
            self.current_index = n - 1
        elif card.type is CardType.DRAW_TWO:
            victim = self.players[0]
            victim.add_cards(self.deck.draw_up_to(2))
            self.events.append(
                GameEvent(
                    EventType.CARD_DRAWN,
                    {"player_id": victim.user_id, "count": 2, "reason": "penalty"},
                )
            )
            self.events.append(GameEvent(EventType.PLAYER_SKIPPED, {"player_id": victim.user_id}))
            self.current_index = 1 % n

        self.transition_to(GameStatus.ACTIVE)
        self.events.append(
            GameEvent(
                EventType.TURN_CHANGED,
                {"player_id": self.current_player_id, "previous_player_id": None},
            )
        )

    def transition_to(self, new_status: GameStatus) -> None:
        if new_status not in ALLOWED_TRANSITIONS[self.status]:
            raise InvalidGameStateError(
                f"Cannot move game from {self.status.value} to {new_status.value}"
            )
        self.status = new_status

    def cancel(self) -> None:
        self.transition_to(GameStatus.CANCELLED)

    def next_index(self, steps: int = 1) -> int:
        """Seat index ``steps`` places ahead in the current direction (modular)."""
        return (self.current_index + self.direction.value * steps) % len(self.players)

    def get_player(self, player_id: int) -> Player:
        """Internal full access to a player (including their hand)."""
        for player in self.players:
            if player.user_id == player_id:
                return player
        raise InvalidPlayerError(f"Player {player_id} is not in this game")

    def drain_events(self) -> list[GameEvent]:
        events, self.events = self.events, []
        return events

    @property
    def player_ids(self) -> list[int]:
        return [p.user_id for p in self.players]

    @property
    def current_player_id(self) -> int:
        return self.players[self.current_index].user_id

    @property
    def top_card(self) -> Card | None:
        return self.deck.top_discard

    @property
    def draw_pile_size(self) -> int:
        return self.deck.draw_size

    @property
    def discard_pile_size(self) -> int:
        return self.deck.discard_size

    @property
    def hand_sizes(self) -> dict[int, int]:
        return {p.user_id: p.hand_size for p in self.players}

    def get_hand(self, player_id: int) -> tuple[Card, ...]:
        """A player's own hand; callers must only show it to that player."""
        return tuple(self.get_player(player_id).hand)

    def get_playable_cards(self, player_id: int) -> tuple[Card, ...]:
        if self.status is not GameStatus.ACTIVE:
            return ()
        return tuple(rules.get_playable_cards(self, self.get_player(player_id)))

    def public_state(self) -> dict[str, Any]:
        top = self.top_card
        return {
            "game_id": self.game_id,
            "status": self.status.value,
            "players": [
                {
                    "user_id": p.user_id,
                    "name": p.name,
                    "hand_size": p.hand_size,
                    "is_active": p.is_active,
                }
                for p in self.players
            ],
            "current_player_id": self.current_player_id,
            "direction": self.direction.value,
            "active_color": self.active_color.value,
            "top_card": top.to_dict() if top else None,
            "draw_pile_size": self.draw_pile_size,
            "discard_pile_size": self.discard_pile_size,
            "winner_id": self.winner_id,
        }

    def _register_uno_window(self, player_id: int) -> None:
        player = self.get_player(player_id)
        if player.hand_size == 1:
            self._uno_window_player_id = player_id
            self.uno_declarations[player_id] = bool(self.config.rules.auto_uno)
            self.uno_vulnerable.pop(player_id, None)
            if self.config.rules.auto_uno:
                self.events.append(GameEvent(EventType.UNO_DECLARED, {"player_id": player_id}))
        else:
            self.uno_declarations.pop(player_id, None)
            self.uno_vulnerable.pop(player_id, None)
            if self._uno_window_player_id == player_id:
                self._uno_window_player_id = None

    def _close_uno_window(self, player_id: int) -> None:
        if player_id == self.current_player_id:
            return
        player = self.get_player(player_id)
        if player.hand_size == 1 and not self.uno_declarations.get(player_id, False):
            self.uno_vulnerable[player_id] = 1
            self.events.append(GameEvent(EventType.UNO_MISSED, {"player_id": player_id}))

    def _apply_missed_uno_penalty(
        self,
        player_id: int,
        *,
        penalty_cards: int | None = None,
    ) -> tuple[GameEvent, ...]:
        if self.uno_vulnerable.get(player_id, 0) == 0:
            raise InvalidGameStateError(f"Player {player_id} is not vulnerable to missed UNO")
        if self.uno_declarations.get(player_id, False):
            self.uno_vulnerable.pop(player_id, None)
            return ()
        cards = self.deck.draw_up_to(
            penalty_cards if penalty_cards is not None else self.config.rules.uno_penalty_cards
        )
        player = self.get_player(player_id)
        player.add_cards(cards)
        self.uno_vulnerable.pop(player_id, None)
        self.uno_declarations.pop(player_id, None)
        event = GameEvent(
            EventType.UNO_PENALTY_APPLIED,
            {"player_id": player_id, "count": len(cards), "reason": "missed_uno"},
        )
        self.events.append(event)
        return (event,)

    def call_uno(self, player_id: int) -> tuple[GameEvent, ...]:
        if self.status is not GameStatus.ACTIVE:
            raise InvalidGameStateError(f"Game is {self.status.value}, not active")
        player = self.get_player(player_id)
        if player.hand_size != 1:
            raise IllegalMoveError("Only players with exactly one card may declare UNO")
        if self._uno_window_player_id is not None and player_id != self._uno_window_player_id:
            raise InvalidTurnError(
                "UNO declarations only apply to the player in the declaration window"
            )
        if self.uno_declarations.get(player_id, False):
            raise IllegalMoveError(f"Player {player_id} already declared UNO")
        self.uno_declarations[player_id] = True
        self.uno_vulnerable.pop(player_id, None)
        self.events.append(GameEvent(EventType.UNO_DECLARED, {"player_id": player_id}))
        return (self.events[-1],)

    def catch_uno(self, caller_id: int, target_player_id: int) -> tuple[GameEvent, ...]:
        if caller_id == target_player_id:
            raise InvalidTurnError("A player cannot catch their own UNO declaration")
        if self.status is not GameStatus.ACTIVE:
            raise InvalidGameStateError(f"Game is {self.status.value}, not active")
        if not self.uno_vulnerable.get(target_player_id):
            raise IllegalMoveError(f"Player {target_player_id} is not vulnerable to UNO penalty")
        if self.uno_declarations.get(target_player_id, False):
            raise IllegalMoveError(f"Player {target_player_id} already declared UNO")
        self.get_player(caller_id)
        penalty_events = self._apply_missed_uno_penalty(target_player_id)
        catch_event = GameEvent(
            EventType.UNO_CAUGHT,
            {"caller_id": caller_id, "target_player_id": target_player_id},
        )
        self.events.append(catch_event)
        return (*penalty_events, catch_event)

    def challenge_wild_draw_four(self, player_id: int) -> tuple[GameEvent, ...]:
        if self.pending_challenge is None:
            raise InvalidGameStateError("There is no pending Wild Draw Four challenge")
        if player_id != self.pending_challenge["challenger_id"]:
            raise InvalidTurnError("Only the next player may challenge a Wild Draw Four")
        offender_id = self.pending_challenge["offender_id"]
        offender = self.get_player(offender_id)
        previous_color = self.pending_challenge.get("previous_color")
        challenge_event = GameEvent(
            EventType.WILD_DRAW_FOUR_CHALLENGED,
            {
                "offender_id": offender_id,
                "challenger_id": player_id,
                "card_id": self.pending_challenge["card_id"],
            },
        )
        self.events.append(challenge_event)
        snapshot_has_color = False
        for entry in self.pending_challenge.get("offender_hand_snapshot", []):
            if isinstance(entry, dict):
                color_name = entry.get("color")
                if color_name and CardColor(color_name) is previous_color:
                    snapshot_has_color = True
                    break
            elif isinstance(entry, str) and offender.has_card(entry):
                if offender.get_card(entry).color is previous_color:
                    snapshot_has_color = True
                    break
        legal = previous_color is None or (
            not snapshot_has_color and not any(c.color is previous_color for c in offender.hand)
        )
        if legal:
            self.pending_challenge = None
            self.events.append(
                GameEvent(
                    EventType.WILD_DRAW_FOUR_CHALLENGE_FAILED,
                    {"challenger_id": player_id},
                )
            )
            challenger = self.get_player(player_id)
            challenger.add_cards(self.deck.draw_up_to(6))
            self.current_index = self.next_index(1)
            self.drawn_card_id = None
            return (challenge_event, self.events[-1])
        offender.add_cards(self.deck.draw_up_to(4))
        self.pending_challenge = None
        self.events.append(
            GameEvent(
                EventType.WILD_DRAW_FOUR_CHALLENGE_SUCCEEDED,
                {"challenger_id": player_id, "offender_id": offender_id},
            )
        )
        self.current_index = self.next_index(1)
        self.drawn_card_id = None
        return (challenge_event, self.events[-1])

    def accept_wild_draw_four(self, player_id: int) -> tuple[GameEvent, ...]:
        if self.pending_challenge is None:
            raise InvalidGameStateError("There is no pending Wild Draw Four to accept")
        if player_id != self.pending_challenge["challenger_id"]:
            raise InvalidTurnError("Only the next player may accept a Wild Draw Four penalty")
        offender_id = self.pending_challenge["offender_id"]
        offender = self.get_player(offender_id)
        offender.add_cards(self.deck.draw_up_to(4))
        self.pending_challenge = None
        self.events.append(
            GameEvent(
                EventType.PENALTY_ACCEPTED,
                {"player_id": player_id, "offender_id": offender_id, "count": 4},
            )
        )
        return (self.events[-1],)

    def stack_penalty(self, player_id: int, card_id: str) -> tuple[GameEvent, ...]:
        if self.pending_penalty is None:
            raise InvalidGameStateError("There is no pending draw penalty")
        if self.pending_penalty["target_player_id"] != player_id:
            raise InvalidTurnError("Only the current target may stack a penalty")
        player = self.get_player(player_id)
        card = player.get_card(card_id)
        if not self.config.rules.stacking_enabled:
            raise IllegalMoveError("Stacking is disabled")
        penalty_type = self.pending_penalty["type"]
        if penalty_type is CardType.DRAW_TWO and not self.config.rules.stack_draw_two:
            raise IllegalMoveError("Draw Two stacking is disabled")
        if penalty_type is CardType.WILD_DRAW_FOUR and not self.config.rules.stack_wild_draw_four:
            raise IllegalMoveError("Wild Draw Four stacking is disabled")
        if (
            card.type is CardType.WILD_DRAW_FOUR
            and penalty_type is CardType.DRAW_TWO
            and not self.config.rules.allow_mixed_stacking
        ):
            raise IllegalMoveError("Mixed stacking is disabled")
        if (
            card.type is CardType.DRAW_TWO
            and penalty_type is CardType.WILD_DRAW_FOUR
            and not self.config.rules.allow_mixed_stacking
        ):
            raise IllegalMoveError("Mixed stacking is disabled")
        if card.type not in {
            penalty_type,
            CardType.DRAW_TWO,
            CardType.WILD_DRAW_FOUR,
        }:
            raise IllegalMoveError("Only compatible penalty cards may be stacked")
        player.remove_card(card_id)
        game_penalty = 2 if card.type is CardType.DRAW_TWO else 4
        self.pending_penalty["count"] += game_penalty
        self.pending_penalty["target_player_id"] = self.next_index(1)
        self.deck.discard(card)
        self.events.append(
            GameEvent(
                EventType.PENALTY_STACKED,
                {
                    "player_id": player_id,
                    "stacked_card": card.to_dict(),
                    "accumulated_count": self.pending_penalty["count"],
                },
            )
        )
        return (self.events[-1],)

    def accept_penalty(self, player_id: int) -> tuple[GameEvent, ...]:
        if self.pending_penalty is None:
            raise InvalidGameStateError("There is no pending draw penalty")
        if self.pending_penalty["target_player_id"] != player_id:
            raise InvalidTurnError("It is not that player's turn to accept the penalty")
        count = self.pending_penalty["count"]
        player = self.get_player(player_id)
        player.add_cards(self.deck.draw_up_to(count))
        self.events.append(
            GameEvent(
                EventType.PENALTY_ACCEPTED,
                {"player_id": player_id, "count": count, "reason": "draw_penalty"},
            )
        )
        self.pending_penalty = None
        return (self.events[-1],)

    def _apply_round_score(self) -> None:
        if self.winner_id is None:
            return
        if not self.config.rules.scoring_enabled:
            return
        if self.round_winner_id is not None:
            return
        winner_id = self.winner_id
        total = 0
        for player in self.players:
            if player.user_id == winner_id:
                continue
            for card in player.hand:
                total += card.value or 0
                if card.type in (CardType.WILD, CardType.WILD_DRAW_FOUR):
                    total += 50
                elif card.type in (CardType.DRAW_TWO, CardType.SKIP, CardType.REVERSE):
                    total += 20
        self.round_scores[winner_id] = self.round_scores.get(winner_id, 0) + total
        self.round_winner_id = winner_id
        self.events.append(
            GameEvent(EventType.ROUND_FINISHED, {"winner_id": winner_id, "points": total})
        )
        self.events.append(
            GameEvent(EventType.SCORE_UPDATED, {"winner_id": winner_id, "points": total})
        )

    def record_match_result(self) -> None:
        if self.round_winner_id is None:
            return
        self.match_scores[self.round_winner_id] = self.match_scores.get(
            self.round_winner_id, 0
        ) + self.round_scores.get(self.round_winner_id, 0)
        if self.match_scores[self.round_winner_id] >= self.config.rules.match_target_score:
            self.match_winner_id = self.round_winner_id
            self.events.append(
                GameEvent(EventType.MATCH_FINISHED, {"winner_id": self.match_winner_id})
            )

    def play_card(
        self, player_id: int, card_id: str, chosen_color: CardColor | str | None = None
    ) -> tuple[GameEvent, ...]:
        return actions.play_card(self, player_id, card_id, chosen_color)

    def draw_card(self, player_id: int) -> DrawResult:
        return actions.draw_card(self, player_id)

    def pass_turn(self, player_id: int) -> tuple[GameEvent, ...]:
        return actions.pass_turn(self, player_id)

    def all_cards(self) -> list[Card]:
        cards = [*self.deck.draw_pile, *self.deck.discard_pile]
        for player in self.players:
            cards.extend(player.hand)
        return cards

    def validate_integrity(self, expected_total: int | None = DECK_SIZE) -> None:
        """Raise if any card exists twice, the total is off, or indexes are corrupt."""
        counts = Counter(c.id for c in self.all_cards())
        dupes = [cid for cid, n in counts.items() if n > 1]
        if dupes:
            raise InvalidGameStateError(f"Cards present more than once: {sorted(dupes)}")
        if expected_total is not None and sum(counts.values()) != expected_total:
            raise InvalidGameStateError(
                f"Expected {expected_total} cards in play, found {sum(counts.values())}"
            )
        if not 0 <= self.current_index < len(self.players):
            raise InvalidGameStateError("current_index out of range")
        if self.status is GameStatus.ACTIVE and self.active_color is CardColor.WILD:
            raise InvalidGameStateError("Active color cannot be WILD")

    @staticmethod
    def _restore_numeric_dict(data: dict[str, Any] | None) -> dict[int, int]:
        if not data:
            return {}
        result: dict[int, int] = {}
        for key, value in data.items():
            result[int(key)] = int(value)
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "status": self.status.value,
            "players": [p.to_dict() for p in self.players],
            "deck": self.deck.to_dict(),
            "current_index": self.current_index,
            "direction": self.direction.value,
            "active_color": self.active_color.value,
            "winner_id": self.winner_id,
            "drawn_card_id": self.drawn_card_id,
            "config": self.config.to_dict(),
            "uno_declarations": {int(k): bool(v) for k, v in self.uno_declarations.items()},
            "uno_vulnerable": {int(k): int(v) for k, v in self.uno_vulnerable.items()},
            "pending_penalty": self.pending_penalty,
            "pending_challenge": self.pending_challenge,
            "round_scores": {int(k): int(v) for k, v in self.round_scores.items()},
            "match_scores": {int(k): int(v) for k, v in self.match_scores.items()},
            "round_winner_id": self.round_winner_id,
            "match_winner_id": self.match_winner_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], rng: random.Random | None = None) -> Game:
        rng = rng or random.Random()
        try:
            config_data = data.get("config", {})
            config = GameConfig.from_dict(config_data)
            players = [Player.from_dict(p) for p in data["players"]]
            round_scores = cls._restore_numeric_dict(data.get("round_scores")) or {
                p.user_id: 0 for p in players
            }
            match_scores = cls._restore_numeric_dict(data.get("match_scores")) or {
                p.user_id: 0 for p in players
            }
            current = cls(
                game_id=data["game_id"],
                players=players,
                deck=Deck.from_dict(data["deck"], rng=rng),
                config=config,
                rng=rng,
                status=GameStatus(data["status"]),
                current_index=data["current_index"],
                direction=Direction(data["direction"]),
                active_color=CardColor(data["active_color"]),
                winner_id=data.get("winner_id"),
                drawn_card_id=data.get("drawn_card_id"),
                uno_declarations=cls._restore_numeric_dict(data.get("uno_declarations")),
                uno_vulnerable=cls._restore_numeric_dict(data.get("uno_vulnerable")),
                pending_penalty=data.get("pending_penalty"),
                pending_challenge=data.get("pending_challenge"),
                round_scores=round_scores,
                match_scores=match_scores,
                round_winner_id=data.get("round_winner_id"),
                match_winner_id=data.get("match_winner_id"),
            )
        except GameError:
            raise
        except (KeyError, ValueError, TypeError) as exc:
            raise InvalidGameStateError(f"Cannot deserialize game: {exc!r}") from exc
        if len({p.user_id for p in current.players}) != len(current.players):
            raise InvalidPlayerError("Duplicate players in serialized game")
        current.validate_integrity(expected_total=None)
        return current
