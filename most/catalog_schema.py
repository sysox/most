"""JSON Schema validation for the curated AI provider catalog."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

CATALOG_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["providers"],
    "properties": {
        "catalog_version": {"type": "integer", "minimum": 1},
        "providers": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "access_methods", "models"],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "access_methods": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["id"],
                            "properties": {"id": {"type": "string", "minLength": 1}},
                        },
                    },
                    "models": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["id", "status", "capabilities"],
                            "properties": {
                                "id": {"type": "string", "minLength": 1},
                                "status": {"enum": ["available", "deprecated", "unavailable", "unknown"]},
                                "capabilities": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                                "is_external_passthrough": {"type": "boolean"},
                            },
                        },
                    },
                },
            },
        },
    },
}


def validate_catalog(catalog: Any) -> dict[str, Any]:
    """Validate a parsed catalog and return it as a mapping."""
    if not isinstance(catalog, dict):
        raise TypeError("catalog must be a mapping")
    errors = sorted(Draft202012Validator(CATALOG_SCHEMA).iter_errors(catalog), key=lambda error: list(error.path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.path) or "catalog"
        raise ValueError(f"invalid catalog at {location}: {error.message}")
    return catalog
