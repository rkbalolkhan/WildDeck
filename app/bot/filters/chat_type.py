"""Chat type filters for message routing."""

from __future__ import annotations

from collections.abc import Sequence

from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message


class ChatTypeFilter(Filter):
    """Filter updates by allowed chat types."""

    def __init__(self, chat_types: Sequence[str] | str) -> None:
        self.chat_types = [chat_types] if isinstance(chat_types, str) else list(chat_types)

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        if isinstance(event, Message):
            chat = event.chat
        else:
            chat = event.message.chat if event.message else None
        if not chat:
            return False
        return chat.type in self.chat_types


class IsPrivateFilter(Filter):
    """Filter updates from private (1-on-1) chats."""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        if isinstance(event, Message):
            chat = event.chat
        else:
            chat = event.message.chat if event.message else None
        return bool(chat and chat.type == "private")


class IsGroupFilter(Filter):
    """Filter updates from group or supergroup chats."""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        if isinstance(event, Message):
            chat = event.chat
        else:
            chat = event.message.chat if event.message else None
        return bool(chat and chat.type in ("group", "supergroup"))
