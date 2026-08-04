"""Failure-triggered provider checks and replacement suggestions."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from .catalog_audit import _model_sort_key, audit_catalog

HEALTH_FILENAME = "provider-health.yaml"


def check_provider_model(catalog_path: Path, discovered_path: Path, provider_id: str, model_id: str) -> dict[str, Any]:
    results, _ = audit_catalog(catalog_path, provider_filter=provider_id, show_models=True, discovered_path=discovered_path)
    model_result = next((result for result in results if result.model_id == model_id), None)
    candidates = [
        result.model_id for result in results
        if result.model_id and "exact model discovered" in result.reason and result.model_id != model_id
    ]
    return {
        "verification": model_result.status if model_result else "unknown",
        "verification_reason": model_result.reason if model_result else "model was not returned by the audit",
        "replacement_candidates": sorted(candidates, key=_model_sort_key)[:10],
    }


def record_failure(data_root: Path, catalog_path: Path, discovered_path: Path, *, provider_id: str,
                   model_id: str, route: str, error: str) -> dict[str, Any]:
    report = check_provider_model(catalog_path, discovered_path, provider_id, model_id)
    record = {
        "failed_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "provider": provider_id, "model": model_id, "route": route, "error": error, **report,
    }
    path = data_root / HEALTH_FILENAME
    data_root.mkdir(parents=True, exist_ok=True)
    current = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    failures = current.get("failures", []) if isinstance(current, dict) else []
    if not isinstance(failures, list):
        failures = []
    failures.append(record)
    path.write_text(yaml.safe_dump({"failures": failures[-100:]}, sort_keys=False), encoding="utf-8")
    return record


def check_recorded_failures(data_root: Path, catalog_path: Path, discovered_path: Path) -> list[dict[str, Any]]:
    path = data_root / HEALTH_FILENAME
    if not path.exists():
        return []
    current = yaml.safe_load(path.read_text(encoding="utf-8"))
    failures = current.get("failures", []) if isinstance(current, dict) else []
    checked = []
    for failure in failures if isinstance(failures, list) else []:
        if not isinstance(failure, dict):
            continue
        provider, model = failure.get("provider"), failure.get("model")
        if isinstance(provider, str) and isinstance(model, str):
            checked.append({**failure, **check_provider_model(catalog_path, discovered_path, provider, model)})
    return checked


def format_health(records: list[dict[str, Any]]) -> str:
    if not records:
        return "no recorded provider failures"
    return "\n".join(
        f"{record.get('provider')}/{record.get('model')}: {record.get('verification')} - "
        f"{record.get('verification_reason')}; replacements: {', '.join(record.get('replacement_candidates', [])) or 'none discovered'}"
        for record in records
    )
