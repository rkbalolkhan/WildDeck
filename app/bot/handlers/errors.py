"""Global error handling foundation."""

import logging

from aiogram import Router
from aiogram.types import ErrorEvent

logger = logging.getLogger(__name__)
router = Router(name="errors")


@router.errors()
async def on_error(event: ErrorEvent) -> bool:
    """Log unhandled handler exceptions with a stack trace and keep the bot alive."""
    logger.error(
        "Unhandled error while processing update %s",
        event.update.update_id,
        exc_info=event.exception,
    )
    return True
