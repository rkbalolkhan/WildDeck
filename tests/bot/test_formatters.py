"""Unit tests for Telegram message formatters."""

from app.bot.formatters import (
    format_about_message,
    format_error,
    format_game_already_exists,
    format_game_cancelled,
    format_game_created,
    format_game_status,
    format_help_message,
    format_no_active_game,
    format_rules_message,
    format_start_message,
    format_unauthorized_cancel,
)


def test_format_start_message_private() -> None:
    text = format_start_message("Alice", is_private=True)
    assert "Alice" in text
    assert "Welcome to WildDeck" in text
    assert "<b>UNO</b>" in text


def test_format_start_message_group() -> None:
    text = format_start_message("Bob", is_private=False)
    assert "Bob" in text
    assert "ready in this group" in text


def test_format_start_message_escapes_html() -> None:
    text = format_start_message("<b>Evil</b>", is_private=True)
    assert "&lt;b&gt;Evil&lt;/b&gt;" in text
    assert "<b>Evil</b>" not in text


def test_format_help_message() -> None:
    text = format_help_message()
    assert "/newgame" in text
    assert "/status" in text
    assert "/cancel" in text
    assert "/rules" in text


def test_format_rules_message() -> None:
    text = format_rules_message()
    assert "Skip" in text
    assert "Reverse" in text
    assert "Draw Two" in text
    assert "Wild Draw Four" in text
    assert "WDF Challenge" in text


def test_format_about_message() -> None:
    text = format_about_message()
    assert "WildDeck UNO Bot" in text
    assert "Phase 05" in text


def test_format_game_created() -> None:
    text = format_game_created("uno_123", "Alice", "group")
    assert "uno_123" in text
    assert "Alice" in text
    assert "group lobby" in text


def test_format_game_status() -> None:
    text = format_game_status(
        game_id="uno_999",
        status="waiting",
        creator_name="Bob",
        player_names=["Bob", "Charlie"],
        current_player="Bob",
        top_card="RED 5",
        draw_pile_count=100,
    )
    assert "uno_999" in text
    assert "Waiting" in text
    assert "Bob" in text
    assert "Charlie" in text
    assert "RED 5" in text
    assert "100" in text


def test_format_game_cancelled() -> None:
    text = format_game_cancelled("uno_123", "Admin")
    assert "uno_123" in text
    assert "Admin" in text
    assert "cancelled" in text


def test_format_game_already_exists() -> None:
    text = format_game_already_exists("uno_456", "Dave")
    assert "uno_456" in text
    assert "Dave" in text
    assert "already in progress" in text


def test_format_no_active_game() -> None:
    text = format_no_active_game()
    assert "No active game" in text


def test_format_unauthorized_cancel() -> None:
    text = format_unauthorized_cancel()
    assert "Permission Denied" in text


def test_format_error() -> None:
    text = format_error("<Database error>")
    assert "&lt;Database error&gt;" in text
