"""Shared builders for engine tests."""

from __future__ import annotations

import itertools
import random

from app.engine import (
    CHOOSABLE_COLORS,
    Card,
    CardColor,
    CardType,
    Deck,
    Direction,
    EventType,
    Game,
    GameConfig,
    GameStatus,
    Player,
    build_standard_cards,
)

R, B, G, Y = CardColor.RED, CardColor.BLUE, CardColor.GREEN, CardColor.YELLOW
_ids = itertools.count(1000)


def mk(color: CardColor, type_: CardType, value: int | None = None) -> Card:
    return Card(f"t{next(_ids)}", color, type_, value)


def num(color: CardColor, value: int) -> Card:
    return mk(color, CardType.NUMBER, value)


def skip(color: CardColor) -> Card:
    return mk(color, CardType.SKIP)


def reverse(color: CardColor) -> Card:
    return mk(color, CardType.REVERSE)


def draw_two(color: CardColor) -> Card:
    return mk(color, CardType.DRAW_TWO)


def wild() -> Card:
    return mk(CardColor.WILD, CardType.WILD)


def wd4() -> Card:
    return mk(CardColor.WILD, CardType.WILD_DRAW_FOUR)


def filler(n: int) -> list[Card]:
    return [num(B if i % 2 else R, i % 10) for i in range(n)]


def make_game(
    hands: list[list[Card]],
    top: Card,
    active_color: CardColor | None = None,
    *,
    current: int = 0,
    direction: Direction = Direction.CLOCKWISE,
    draw_pile: list[Card] | None = None,
) -> Game:
    """Hand-built ACTIVE game. Players have ids 100, 101, ... ; draw pile pops from its end."""
    players = [Player(100 + i, f"P{i}", list(h)) for i, h in enumerate(hands)]
    rng = random.Random(0)
    deck = Deck(draw_pile if draw_pile is not None else filler(20), [top], rng=rng)
    return Game(
        game_id="g",
        players=players,
        deck=deck,
        config=GameConfig(),
        rng=rng,
        status=GameStatus.ACTIVE,
        current_index=current,
        direction=direction,
        active_color=active_color or top.color,
    )


def rigged_deck(n_players: int, target: Card, rng: random.Random) -> Deck:
    """Standard deck where ``target`` is the card flipped right after dealing 7 each."""
    rest = [c for c in build_standard_cards() if c.id != target.id]
    rng.shuffle(rest)
    rest.insert(len(rest) - n_players * 7, target)
    return Deck(rest, [], rng=rng)


def simulate(seed: int, max_steps: int = 5000) -> dict[str, int]:
    """Play one full random-legal-move game, asserting invariants after every step."""
    rng = random.Random(seed)
    n = rng.randint(2, 10)
    game = Game.new([Player(1000 + i, f"P{i}") for i in range(n)], rng=random.Random(seed + 7))
    game.validate_integrity()
    steps = 0
    while game.status is GameStatus.ACTIVE:
        steps += 1
        assert steps <= max_steps, "game did not finish"
        pid, prev_index = game.current_player_id, game.current_index
        game.drain_events()
        if game.drawn_card_id is not None:
            card = game.get_player(pid).get_card(game.drawn_card_id)
            if rng.random() < 0.9:
                color = rng.choice(CHOOSABLE_COLORS) if card.is_wild else None
                game.play_card(pid, card.id, color)
            else:
                game.pass_turn(pid)
        else:
            playable = game.get_playable_cards(pid)
            if playable and rng.random() < 0.85:
                card = rng.choice(playable)
                color = rng.choice(CHOOSABLE_COLORS) if card.is_wild else None
                game.play_card(pid, card.id, color)
            else:
                game.draw_card(pid)
        game.validate_integrity()
        turns = [e for e in game.drain_events() if e.type is EventType.TURN_CHANGED]
        assert len(turns) <= 1
        if game.status is GameStatus.FINISHED:
            assert not turns
        elif turns:
            assert turns[0].data["previous_player_id"] == pid
            assert turns[0].data["player_id"] == game.current_player_id
        else:
            assert game.current_index == prev_index and game.drawn_card_id is not None
    assert game.status is GameStatus.FINISHED
    sizes = game.hand_sizes
    assert game.winner_id in sizes and sizes[game.winner_id] == 0
    assert sum(1 for s in sizes.values() if s == 0) == 1
    return {"players": n, "steps": steps}
