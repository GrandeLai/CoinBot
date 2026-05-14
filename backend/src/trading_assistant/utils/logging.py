"""Loguru setup with simple sensitive value redaction."""

from __future__ import annotations

import sys
from collections.abc import Iterable

from loguru import logger


SENSITIVE_TOKENS = ("api_key", "api_secret", "passphrase", "secret", "token")


def redact_text(text: str, extra_values: Iterable[str] = ()) -> str:
    """Redact common secret markers and known sensitive values from text."""
    redacted = text
    for value in extra_values:
        if value:
            redacted = redacted.replace(value, "***redacted***")
    for token in SENSITIVE_TOKENS:
        redacted = redacted.replace(token, "***redacted***")
    return redacted


def configure_logging(level: str = "INFO") -> None:
    """Configure loguru for concise stderr logs."""
    logger.remove()
    logger.add(sys.stderr, level=level.upper(), format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")

