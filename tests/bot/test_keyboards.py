"""Unit tests for inline keyboard builders and callback factories."""

from app.bot.keyboards import (
    GameAction,
    MenuAction,
    about_keyboard,
    game_conflict_keyboard,
    game_created_keyboard,
    game_status_keyboard,
    help_keyboard,
    rules_keyboard,
    start_keyboard,
)


def test_menu_action_callback_pack_unpack() -> None:
    data = MenuAction(action="rules")
    packed = data.pack()
    assert packed.startswith("menu:")
    unpacked = MenuAction.unpack(packed)
    assert unpacked.action == "rules"


def test_game_action_callback_pack_unpack() -> None:
    data = GameAction(action="cancel", game_id="uno_12345")
    packed = data.pack()
    assert packed.startswith("game:")
    unpacked = GameAction.unpack(packed)
    assert unpacked.action == "cancel"
    assert unpacked.game_id == "uno_12345"


def test_start_keyboard_private() -> None:
    kb = start_keyboard(is_private=True, bot_username="WildDeckBot")
    assert any(
        button.url == "https://t.me/WildDeckBot?startgroup=true"
        for row in kb.inline_keyboard
        for button in row
    )


def test_start_keyboard_group() -> None:
    kb = start_keyboard(is_private=False)
    # Group mode should not show the "Add to Group" URL button
    assert not any(button.url is not None for row in kb.inline_keyboard for button in row)


def test_help_rules_about_keyboards() -> None:
    help_kb = help_keyboard()
    assert len(help_kb.inline_keyboard) > 0

    rules_kb = rules_keyboard()
    assert len(rules_kb.inline_keyboard) > 0

    about_kb = about_keyboard()
    assert len(about_kb.inline_keyboard) > 0


def test_game_created_keyboard() -> None:
    kb = game_created_keyboard("uno_abc")
    buttons = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert any(b == GameAction(action="status", game_id="uno_abc").pack() for b in buttons)
    assert any(b == GameAction(action="cancel", game_id="uno_abc").pack() for b in buttons)


def test_game_status_keyboard() -> None:
    kb = game_status_keyboard("uno_xyz")
    buttons = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert any(b == GameAction(action="status", game_id="uno_xyz").pack() for b in buttons)
    assert any(b == GameAction(action="cancel", game_id="uno_xyz").pack() for b in buttons)


def test_game_conflict_keyboard() -> None:
    kb = game_conflict_keyboard("uno_conflict")
    buttons = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert any(b == GameAction(action="status", game_id="uno_conflict").pack() for b in buttons)
    assert any(b == GameAction(action="cancel", game_id="uno_conflict").pack() for b in buttons)
