"""HTML message templates and formatters for Telegram updates."""

from __future__ import annotations

import html


def format_start_message(user_name: str, is_private: bool = True) -> str:
    """Format welcome greeting for /start command."""
    safe_name = html.escape(user_name)
    if is_private:
        return (
            f"👋 <b>Welcome to WildDeck, {safe_name}!</b>\n\n"
            "WildDeck is a premium multiplayer <b>UNO</b> card game engine for Telegram.\n\n"
            "🎮 <b>How to play:</b>\n"
            "• Add me to a Telegram group with your friends.\n"
            "• Type /newgame in the group to start a game lobby.\n"
            "• Play cards, shout UNO, challenge Wild Draw Fours, and win!\n\n"
            "Use the buttons below to explore the official rules or available commands."
        )
    return (
        f"👋 <b>Hello {safe_name}! WildDeck is ready in this group.</b>\n\n"
        "Type /newgame to create a new UNO lobby, or /help to see all commands."
    )


def format_help_message() -> str:
    """Format help text listing all available commands and their usage."""
    return (
        "📖 <b>WildDeck — Command Guide</b>\n\n"
        "<b>Game Commands:</b>\n"
        "• /newgame — Create a new UNO game lobby in this chat\n"
        "• /status — Check the current game status, players, and turn\n"
        "• /cancel — Cancel the ongoing game (creator or group admin)\n\n"
        "<b>Information Commands:</b>\n"
        "• /rules — View complete UNO rules and mechanics\n"
        "• /about — Information about the WildDeck project\n"
        "• /help — Show this help message\n\n"
        "💡 <i>Tip: WildDeck fully enforces official UNO card mechanics and penalties!</i>"
    )


def format_rules_message() -> str:
    """Format comprehensive UNO rules matching the engine mechanics."""
    return (
        "📜 <b>Official UNO Rules & Mechanics</b>\n\n"
        "<b>Goal:</b>\n"
        "Be the first player to play all cards from your hand!\n\n"
        "<b>Gameplay:</b>\n"
        "• Match cards by <b>Color</b>, <b>Number</b>, or <b>Action Type</b>.\n"
        "• If you have no playable card, you must draw from the draw pile.\n\n"
        "<b>Special Action Cards:</b>\n"
        "• <b>Skip (🚫):</b> Next player loses their turn.\n"
        "• <b>Reverse (🔄):</b> Reverses play direction (or acts as Skip in 2-player games).\n"
        "• <b>Draw Two (+2):</b> Next player draws 2 cards and skips their turn.\n"
        "• <b>Wild (🌈):</b> Choose the active color.\n"
        "• <b>Wild Draw Four (+4):</b> Choose active color; next player draws 4 cards.\n\n"
        "<b>Penalties & Challenges:</b>\n"
        "• <b>UNO Call:</b> Call UNO when you have 1 card left, or get penalized 2 cards!\n"
        "• <b>WDF Challenge:</b> If challenged on +4, challenger wins if the play was illegal!"
    )


def format_about_message() -> str:
    """Format about information."""
    return (
        "🃏 <b>WildDeck UNO Bot</b>\n\n"
        "A premium, asynchronous, high-concurrency Telegram UNO engine built with Python 3.12+, "
        "Aiogram 3, and PostgreSQL.\n\n"
        "• <b>Features:</b> Full official rules, tournament scoring, robust persistence.\n"
        "• <b>Status:</b> Phase 05 Telegram Bot Integration."
    )


def format_game_created(game_id: str, creator_name: str, chat_type: str) -> str:
    """Format announcement for newly created game."""
    safe_creator = html.escape(creator_name)
    safe_game_id = html.escape(game_id)
    chat_label = "private session" if chat_type == "private" else "group lobby"
    return (
        f"🎮 <b>New UNO Game Created!</b>\n\n"
        f"• <b>Game ID:</b> <code>{safe_game_id}</code>\n"
        f"• <b>Creator:</b> {safe_creator}\n"
        f"• <b>Type:</b> {chat_label}\n"
        f"• <b>Status:</b> Waiting for players\n\n"
        "<i>Use /status to monitor game progress or the buttons below.</i>"
    )


def format_game_status(
    game_id: str,
    status: str,
    creator_name: str,
    player_names: list[str],
    current_player: str | None = None,
    top_card: str | None = None,
    draw_pile_count: int | None = None,
) -> str:
    """Format active game status summary."""
    safe_game_id = html.escape(game_id)
    safe_creator = html.escape(creator_name)
    safe_status = html.escape(status.capitalize())

    lines = [
        f"📊 <b>Game Status: <code>{safe_game_id}</code></b>\n",
        f"• <b>Status:</b> {safe_status}",
        f"• <b>Creator:</b> {safe_creator}",
        f"• <b>Players ({len(player_names)}):</b> "
        + ", ".join(html.escape(p) for p in player_names),
    ]

    if top_card:
        lines.append(f"• <b>Top Card:</b> <code>{html.escape(top_card)}</code>")
    if current_player:
        lines.append(f"• <b>Current Turn:</b> {html.escape(current_player)}")
    if draw_pile_count is not None:
        lines.append(f"• <b>Cards in Draw Pile:</b> {draw_pile_count}")

    return "\n".join(lines)


def format_game_cancelled(game_id: str, cancelled_by: str) -> str:
    """Format message when game is cancelled."""
    safe_game_id = html.escape(game_id)
    safe_user = html.escape(cancelled_by)
    return (
        f"🛑 <b>Game Cancelled</b>\n\n"
        f"Game <code>{safe_game_id}</code> has been cancelled by {safe_user}.\n"
        "You can start a new game anytime with /newgame."
    )


def format_game_already_exists(game_id: str, creator_name: str) -> str:
    """Format notification when /newgame is run but a game is already active."""
    safe_game_id = html.escape(game_id)
    safe_creator = html.escape(creator_name)
    return (
        f"⚠️ <b>A game is already in progress in this chat!</b>\n\n"
        f"• <b>Game ID:</b> <code>{safe_game_id}</code>\n"
        f"• <b>Created by:</b> {safe_creator}\n\n"
        "Use /status to view the active game, or /cancel to abort it first."
    )


def format_no_active_game() -> str:
    """Format response when querying status or cancelling with no active game."""
    return "ℹ️ <b>No active game in this chat.</b>\n\nStart a new UNO match by typing /newgame!"


def format_unauthorized_cancel() -> str:
    """Format refusal when unauthorized user attempts /cancel."""
    return (
        "🚫 <b>Permission Denied</b>\n\n"
        "Only the player who created the game or a chat administrator can cancel it."
    )


def format_error(message: str) -> str:
    """Format user-facing error message."""
    safe_message = html.escape(message)
    return f"⚠️ <b>Error:</b> {safe_message}"
