"""Secret-safe logging helpers."""

from __future__ import annotations

import re
from typing import Any

DEFAULT_SECRET_PATTERNS = (
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(password\s*[:=]\s*)[^\s,;]+"),
)


def redact_text(value: str, secrets: tuple[str, ...] = (), patterns=DEFAULT_SECRET_PATTERNS) -> str:
    redacted = value
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "<redacted>")
    for pattern in patterns:
        redacted = pattern.sub(r"\1<redacted>", redacted)
    return redacted


def redact_value(value: Any, secrets: tuple[str, ...] = ()) -> Any:
    if isinstance(value, str):
        return redact_text(value, secrets)
    if isinstance(value, dict):
        return {key: redact_value(item, secrets) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_value(item, secrets) for item in value]
    return value
