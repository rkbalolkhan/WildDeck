"""Standard UNO matching and legality rules. Pure functions, no state mutation."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from app.engine.card import Card, CardColor, CardType
from app.engine.errors import IllegalMoveError

if TYPE_CHECKING:
    from app.engine.game import Game
    from app.engine.player import Player

MIN_PLAYERS = 2
MAX_PLAYERS = 10
INITIAL_HAND_SIZE = 7


def matches(card: Card, top_card: Card, active_color: CardColor) -> bool:
    """Color / number / action-type match. Wild cards are handled by the caller."""
    if card.color is active_color:
        return True
    if card.type is CardType.NUMBER:
        return top_card.type is CardType.NUMBER and card.value == top_card.value
    return card.is_action and card.type is top_card.type


def may_play_wild_draw_four(hand: Iterable[Card], active_color: CardColor) -> bool:
    """Wild Draw Four is legal only with no card of the active color in hand."""
    return not any(c.color is active_color for c in hand)


def is_card_playable(
    card: Card, hand: Iterable[Card], top_card: Card, active_color: CardColor
) -> bool:
    """Legality of ``card`` on ``top_card`` given the active color and the holder's hand."""
    if card.type is CardType.WILD:
        return True
    if card.type is CardType.WILD_DRAW_FOUR:
        return may_play_wild_draw_four(hand, active_color)
    return matches(card, top_card, active_color)


def _constrained_by_draw(game: Game, card: Card, player: Player) -> bool:
    """After drawing, only the drawn card may be played."""
    return (
        game.drawn_card_id is not None
        and player.user_id == game.current_player_id
        and card.id != game.drawn_card_id
    )


def is_playable(card: Card, game: Game, player: Player) -> bool:
    """Whether ``player`` could legally play ``card`` now (turn order not checked)."""
    top = game.top_card
    if top is None or not player.has_card(card.id) or _constrained_by_draw(game, card, player):
        return False
    return is_card_playable(card, player.hand, top, game.active_color)


def get_playable_cards(game: Game, player: Player) -> list[Card]:
    return [c for c in player.hand if is_playable(c, game, player)]


def validate_play(card: Card, game: Game, player: Player) -> None:
    """Raise :class:`IllegalMoveError` with a specific reason if the play is illegal."""
    if _constrained_by_draw(game, card, player):
        raise IllegalMoveError("After drawing you may only play the card you drew, or pass")
    top = game.top_card
    if top is None:
        raise IllegalMoveError("There is no card on the discard pile")
    if card.type is CardType.WILD_DRAW_FOUR:
        if not may_play_wild_draw_four(player.hand, game.active_color):
            raise IllegalMoveError(
                f"Wild Draw Four is only legal with no {game.active_color.value} card in hand"
            )
        return
    if not is_card_playable(card, player.hand, top, game.active_color):
        raise IllegalMoveError(
            f"{card.type.value} {card.color.value} does not match "
            f"{game.active_color.value} / {top.type.value}"
        )
