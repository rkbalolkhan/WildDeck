"""Context extraction and encapsulation for Telegram events."""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any

from aiogram.types import CallbackQuery, Message, User


@dataclass(frozen=True, slots=True)
class TelegramContext:
    """Normalized context extracted from a Telegram Message or CallbackQuery."""

    user_id: int
    user_name: str
    username: str | None
    chat_id: int
    chat_type: str
    thread_id: int | None = None
    message_id: int | None = None

    @property
    def is_private(self) -> bool:
        """True if the event originated from a 1-on-1 private chat."""
        return self.chat_type == "private"

    @property
    def is_group(self) -> bool:
        """True if the event originated from a group or supergroup chat."""
        return self.chat_type in ("group", "supergroup")

    @classmethod
    def sanitize_name(cls, user: User | None) -> str:
        """Extract and HTML-escape a user's display name."""
        if not user:
            return "Player"
        name = user.full_name.strip() or user.first_name.strip() or "Player"
        return html.escape(name)

    @classmethod
    def from_message(cls, message: Message) -> TelegramContext:
        """Construct context from an incoming Message."""
        user = message.from_user
        user_id = user.id if user else 0
        user_name = cls.sanitize_name(user)
        username = user.username if user else None
        chat = message.chat

        return cls(
            user_id=user_id,
            user_name=user_name,
            username=username,
            chat_id=chat.id,
            chat_type=chat.type,
            thread_id=message.message_thread_id,
            message_id=message.message_id,
        )

    @classmethod
    def from_callback(cls, callback: CallbackQuery) -> TelegramContext:
        """Construct context from an incoming CallbackQuery."""
        user = callback.from_user
        user_id = user.id
        user_name = cls.sanitize_name(user)
        username = user.username

        # Chat and message info come from callback.message when available
        msg = callback.message
        if msg and hasattr(msg, "chat"):
            chat_id = msg.chat.id
            chat_type = msg.chat.type
            thread_id = getattr(msg, "message_thread_id", None)
            message_id = getattr(msg, "message_id", None)
        else:
            # Fallback for inline callbacks without an attached message
            chat_id = user_id
            chat_type = "private"
            thread_id = None
            message_id = None

        return cls(
            user_id=user_id,
            user_name=user_name,
            username=username,
            chat_id=chat_id,
            chat_type=chat_type,
            thread_id=thread_id,
            message_id=message_id,
        )

    def to_metadata(self) -> dict[str, Any]:
        """Convert to a serializable dictionary for persistent storage."""
        return {
            "chat_id": self.chat_id,
            "chat_type": self.chat_type,
            "creator_id": self.user_id,
            "creator_name": self.user_name,
            "thread_id": self.thread_id,
        }
