"""Domain exceptions raised by the UNO engine."""


class GameError(Exception):
    """Base class for every expected engine failure."""


class InvalidPlayerError(GameError):
    """Unknown, duplicate or otherwise invalid player."""


class InvalidTurnError(GameError):
    """A player acted when it was not their turn."""


class InvalidCardError(GameError):
    """Malformed card, or a card the player does not hold."""


class IllegalMoveError(GameError):
    """A well-formed move that violates the UNO rules."""


class InvalidColorError(GameError):
    """Missing, unexpected or unusable chosen color."""


class InvalidGameStateError(GameError):
    """Action not allowed in the current game status, or corrupt state."""


class InvalidDrawError(GameError):
    """Nonsensical draw request (for example drawing zero cards)."""


class DeckEmptyError(GameError):
    """Not enough cards left, even after recycling the discard pile."""
