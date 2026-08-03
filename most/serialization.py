"""Canonical serialization helpers and persisted-record validation."""

from __future__ import annotations

from enum import Enum
from typing import Any

from .models import PersistedRecordHeader, utc_now


def canonicalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): canonicalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonicalize(item) for item in value]
    return value


def versioned_payload(payload: dict[str, Any], *, record_type: str, record_id: str,
                     application_version: str = "0.1.0", schema_version: int = 1) -> dict[str, Any]:
    header = PersistedRecordHeader(schema_version, record_type, record_id, utc_now(), application_version)
    header_data = {
        "schema_version": header.schema_version,
        "record_type": header.record_type,
        "record_id": header.record_id,
        "written_at": header.written_at,
        "writer_application_version": header.writer_application_version,
    }
    return {**header_data, **canonicalize(payload)}


def validate_header(payload: dict[str, Any]) -> PersistedRecordHeader:
    required = {"schema_version", "record_type", "record_id", "written_at", "writer_application_version"}
    missing = required - payload.keys()
    if missing:
        raise ValueError(f"persisted record missing header fields: {sorted(missing)}")
    return PersistedRecordHeader(
        int(payload["schema_version"]), str(payload["record_type"]),
        str(payload["record_id"]), str(payload["written_at"]),
        str(payload["writer_application_version"]),
    )
