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
    return errors


def require_valid_ai_configuration(configuration: dict[str, Any]) -> None:
    errors = validate_ai_configuration(configuration)
    if errors:
        raise ValueError("invalid AI configuration: " + "; ".join(errors))
