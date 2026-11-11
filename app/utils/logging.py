"""Centralised logging with secret redaction."""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import Iterable

_TOKEN_RE = re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b")
_URL_CREDS_RE = re.compile(r"(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*://)(?P<user>[^:/@\s]+):[^@\s]+@")
REDACTED = "***"

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def redact(text: str, secrets: Iterable[str] = ()) -> str:
    """Mask bot tokens, URL credentials and any explicitly registered secrets."""
    text = _TOKEN_RE.sub(REDACTED, text)
    text = _URL_CREDS_RE.sub(rf"\g<scheme>\g<user>:{REDACTED}@", text)
    for secret in secrets:
        if secret:
            text = text.replace(secret, REDACTED)
    return text


class RedactingFormatter(logging.Formatter):
    """Formatter that redacts the final rendered record, stack traces included."""

    def __init__(self, secrets: Iterable[str] = ()) -> None:
        super().__init__(LOG_FORMAT, DATE_FORMAT)
        self._secrets = tuple(secrets)

    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record), self._secrets)


def setup_logging(level: str = "INFO", secrets: Iterable[str] = ()) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(RedactingFormatter(secrets))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    third_party = logging.DEBUG if level == "DEBUG" else logging.WARNING
    logging.getLogger("sqlalchemy.engine").setLevel(third_party)
    logging.getLogger("aiohttp.access").setLevel(third_party)
