"""Validated, source-backed pricing updates for the AI catalog."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

from .catalog_schema import validate_catalog


def apply_pricing_updates(catalog_path: Path, updates_path: Path, *, update: bool = False) -> dict[str, Any]:
    catalog = validate_catalog(yaml.safe_load(catalog_path.read_text(encoding="utf-8")))
    updates = yaml.safe_load(updates_path.read_text(encoding="utf-8"))
    if not isinstance(catalog, dict) or not isinstance(updates, dict):
        raise TypeError("catalog and pricing updates must be YAML mappings")
    entries = updates.get("prices")
    if not isinstance(entries, list):
        raise TypeError("pricing updates must contain a prices list")

    providers = {str(provider.get("id")): provider for provider in catalog.get("providers", []) if isinstance(provider, dict)}
    for entry in entries:
        _validate_entry(entry)
        provider = providers.get(str(entry["provider_id"]))
        if provider is None:
            raise ValueError(f"unknown provider: {entry['provider_id']}")
        model = next((item for item in provider.get("models", [])
                      if isinstance(item, dict) and item.get("id") == entry["model_id"]), None)
        if model is None:
            raise ValueError(f"model is not in catalog: {entry['provider_id']}/{entry['model_id']}")
        model["pricing"] = {
            "per_1m_tokens": dict(entry["per_1m_tokens"]),
            "source": {"url": entry["source"]["url"], "checked_at": entry["source"]["checked_at"]},
        }

    if update:
        catalog["pricing_last_updated"] = datetime.now(UTC).date().isoformat()
        catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return catalog


def _validate_entry(entry: Any) -> None:
    if not isinstance(entry, dict):
        raise TypeError("each pricing entry must be a mapping")
    required = {"provider_id", "model_id", "per_1m_tokens", "source"}
    missing = required - entry.keys()
    if missing:
        raise ValueError(f"pricing entry missing fields: {sorted(missing)}")
    prices = entry["per_1m_tokens"]
    if not isinstance(prices, dict) or not {"input", "output"} <= prices.keys():
        raise ValueError("per_1m_tokens must contain input and output")
    for key, value in prices.items():
        if value is not None and (not isinstance(value, (int, float)) or value < 0):
            raise ValueError(f"invalid price for {key}: {value!r}")
    source = entry["source"]
    if not isinstance(source, dict) or not str(source.get("url", "")).startswith("https://"):
        raise ValueError("pricing source must contain an HTTPS url")
    date.fromisoformat(str(source.get("checked_at", "")))
