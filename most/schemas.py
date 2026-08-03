"""Strict validation for persisted MVP configuration records."""

from __future__ import annotations

from typing import Any

from .models import OverflowPolicy


def validate_ai_configuration(configuration: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("id", "name", "provider_id", "access_method_id"):
        if not configuration.get(field):
            errors.append(f"{field} is required")
    location = configuration.get("location")
    if location not in {"local", "remote-private", "remote-public", "provider-cloud", "browser-session"}:
        errors.append("location is not a supported value")
    overflow = configuration.get("context_overflow_policy", OverflowPolicy.FAIL)
    try:
        OverflowPolicy(overflow)
    except (ValueError, TypeError):
        errors.append("context_overflow_policy is not supported")
    if not isinstance(configuration.get("adapter_options", {}), dict):
        errors.append("adapter_options must be an object")
    if _contains_plaintext_secret(configuration.get("adapter_options", {})):
        errors.append("plaintext credentials must use credential_reference and a secret-store handle")
    return errors


def require_valid_ai_configuration(configuration: dict[str, Any]) -> None:
    errors = validate_ai_configuration(configuration)
    if errors:
        raise ValueError("invalid AI configuration: " + "; ".join(errors))


def _contains_plaintext_secret(value: object, *, key: str = "") -> bool:
    lowered = key.lower()
    if any(marker in lowered for marker in ("api_key", "apikey", "password", "secret", "access_token", "private_key")):
        return value not in (None, "", "<redacted>")
    if isinstance(value, dict):
        return any(_contains_plaintext_secret(item, key=str(name)) for name, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_plaintext_secret(item, key=key) for item in value)
    return False
