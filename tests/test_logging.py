import logging
import sys

from app.utils.logging import RedactingFormatter, redact


def test_redacts_bot_token_and_url_password() -> None:
    out = redact("token 123456:ABCdefGHIjklMNOpqrSTUvwx and postgresql://u:hunter2@h/db")
    assert "ABCdef" not in out and "hunter2" not in out
    assert "postgresql://u:***@h/db" in out


def test_formatter_redacts_exception_trace() -> None:
    try:
        raise RuntimeError("secret-xyz")
    except RuntimeError:
        rec = logging.LogRecord("t", logging.ERROR, "f", 1, "boom", None, sys.exc_info())
    out = RedactingFormatter(secrets=["secret-xyz"]).format(rec)
    assert "secret-xyz" not in out and "Traceback" in out
