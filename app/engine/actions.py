"""State-changing operations. Every action validates fully *before* mutating anything."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.engine import rules
from app.engine.card import Card, CardColor, CardType
from app.engine.errors import (
    IllegalMoveError,
    InvalidColorError,
    InvalidGameStateError,
    InvalidTurnError,
)
from app.engine.events import EventType, GameEvent
from app.engine.player import Player
from app.engine.state import GameStatus

if TYPE_CHECKING:
    from app.engine.game import Game


@dataclass(frozen=True, slots=True)
class DrawResult:
    """Outcome of :func:`draw_card`. ``card`` is private to the drawing player."""

    card: Card | None
    can_play: bool
    events: tuple[GameEvent, ...]


def require_turn(game: Game, player_id: int) -> Player:
    """Validate status, player existence and turn ownership; return the player."""
    if game.status is not GameStatus.ACTIVE:
        raise InvalidGameStateError(f"Game is {game.status.value}, not active")
    player = game.get_player(player_id)
    if game.current_player_id != player_id:
        raise InvalidTurnError(f"It is not player {player_id}'s turn")
    return player


def _resolve_color(card: Card, chosen: CardColor | str | None) -> CardColor:
    if chosen is not None and not isinstance(chosen, CardColor):
        try:
            chosen = CardColor(chosen)
        except ValueError as exc:
            raise InvalidColorError(f"Unknown color {chosen!r}") from exc
    if card.is_wild:
        if chosen is None or chosen is CardColor.WILD:
            raise InvalidColorError("Wild cards need a chosen color: red, blue, green or yellow")
        return chosen
    if chosen is not None:
        raise InvalidColorError("chosen_color is only allowed with wild cards")
    return card.color


def _advance(game: Game, steps: int, events: list[GameEvent]) -> None:
    previous = game.current_player_id
    previous_player = game.get_player(previous)
    if (
        previous_player.hand_size == 1
        and game.config.rules.uno_penalty_enabled
        and not game.uno_declarations.get(previous_player.user_id, False)
    ):
        game.uno_vulnerable[previous_player.user_id] = 1
        events.append(GameEvent(EventType.UNO_MISSED, {"player_id": previous_player.user_id}))

    game.current_index = game.next_index(steps)
    game.drawn_card_id = None
    game._uno_window_player_id = None
    events.append(
        GameEvent(
            EventType.TURN_CHANGED,
            {"player_id": game.current_player_id, "previous_player_id": previous},
        )
    )


def _penalty_draw(game: Game, victim: Player, count: int, events: list[GameEvent]) -> None:
    cards = game.deck.draw_up_to(count)
    victim.add_cards(cards)
    events.append(
        GameEvent(
            EventType.CARD_DRAWN,
            {"player_id": victim.user_id, "count": len(cards), "reason": "penalty"},
        )
    )


def _skip_event(player_id: int) -> GameEvent:
    return GameEvent(EventType.PLAYER_SKIPPED, {"player_id": player_id})


def _apply_effect(game: Game, card: Card, events: list[GameEvent]) -> int:
    """Apply a played card's effect; return how many seats the turn should advance."""
    if card.type is CardType.SKIP:
        events.append(_skip_event(game.player_ids[game.next_index(1)]))
        return 2
    if card.type is CardType.REVERSE:
        game.direction = game.direction.reversed()
        events.append(GameEvent(EventType.DIRECTION_CHANGED, {"direction": game.direction.value}))
        if len(game.player_ids) == 2:  # Reverse acts like Skip with two players
            events.append(_skip_event(game.player_ids[game.next_index(1)]))
            return 2
        return 1
    if card.type in (CardType.DRAW_TWO, CardType.WILD_DRAW_FOUR):
        count = 2 if card.type is CardType.DRAW_TWO else 4
        victim_index = game.next_index(1)
        _penalty_draw(game, game.players[victim_index], count, events)
        events.append(_skip_event(game.player_ids[victim_index]))
        return 2
    return 1


def play_card(
    game: Game, player_id: int, card_id: str, chosen_color: CardColor | str | None = None
) -> tuple[GameEvent, ...]:
    player = require_turn(game, player_id)
    card = player.get_card(card_id)
    rules.validate_play(card, game, player)
    new_color = _resolve_color(card, chosen_color)

    events: list[GameEvent] = []
    old_color = game.active_color
    offender_hand_snapshot = [card.to_dict() for card in player.hand]
    player.remove_card(card_id)
    game.deck.discard(card)
    game.drawn_card_id = None
    events.append(
        GameEvent(
            EventType.CARD_PLAYED,
            {
                "player_id": player_id,
                "card": card.to_dict(),
                "chosen_color": new_color.value if card.is_wild else None,
            },
        )
    )
    game.active_color = new_color
    if new_color is not old_color:
        events.append(GameEvent(EventType.COLOR_CHANGED, {"color": new_color.value}))

    if (
        player.hand_size == 0
        and card.type is CardType.WILD_DRAW_FOUR
        and game.config.rules.wild_draw_four_challenge
    ):
        challenger_id = game.players[game.next_index(1)].user_id
        game.pending_challenge = {
            "challenger_id": challenger_id,
            "offender_id": player_id,
            "card_id": card.id,
            "offender_hand_snapshot": offender_hand_snapshot,
            "previous_color": old_color,
        }
        game.pending_penalty = {
            "type": CardType.WILD_DRAW_FOUR,
            "count": 4,
            "target_player_id": challenger_id,
        }
        game.current_index = game.next_index(1)
        game.events.extend(events)
        return tuple(events)

    game._register_uno_window(player_id)
    steps = _apply_effect(game, card, events)
    if player.hand_size == 0:
        game.winner_id = player_id
        game.transition_to(GameStatus.FINISHED)
        events.append(GameEvent(EventType.GAME_FINISHED, {"winner_id": player_id}))
    else:
        _advance(game, steps, events)
    game.events.extend(events)
    return tuple(events)


def draw_card(game: Game, player_id: int) -> DrawResult:
    player = require_turn(game, player_id)
    if game.drawn_card_id is not None:
        raise IllegalMoveError("You already drew this turn: play the drawn card or pass")

    events: list[GameEvent] = []
    if game.deck.available == 0:  # nothing left anywhere: the turn simply passes
        _advance(game, 1, events)
        game.events.extend(events)
        return DrawResult(None, False, tuple(events))

    card = game.deck.draw(1)[0]
    player.add_card(card)
    game._register_uno_window(player_id)
    events.append(
        GameEvent(EventType.CARD_DRAWN, {"player_id": player_id, "count": 1, "reason": "draw"})
    )
    top = game.top_card
    assert top is not None
    can_play = rules.is_card_playable(card, player.hand, top, game.active_color)
    if can_play:
        game.drawn_card_id = card.id  # same player keeps the turn
    else:
        _advance(game, 1, events)
    game.events.extend(events)
    return DrawResult(card, can_play, tuple(events))


def pass_turn(game: Game, player_id: int) -> tuple[GameEvent, ...]:
    """End the turn after drawing a playable card the player chose not to play."""
    require_turn(game, player_id)
    if game.drawn_card_id is None:
        raise IllegalMoveError("You can only pass after drawing a card")
    events: list[GameEvent] = []
    _advance(game, 1, events)
    game.events.extend(events)
    return tuple(events)
