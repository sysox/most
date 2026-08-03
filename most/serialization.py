"""Canonical serialization helpers and persisted-record validation."""

from __future__ import annotations

from collections.abc import Callable
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


class UnsupportedSchemaError(ValueError):
    pass


class SchemaRegistry:
    """Dispatches persisted records by `(record_type, schema_version)`."""

    def __init__(self):
        self._readers: dict[tuple[str, int], Callable[[dict[str, Any]], dict[str, Any]]] = {}

    def register(self, record_type: str, schema_version: int,
                 reader: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        key = (record_type, schema_version)
        if key in self._readers:
            raise ValueError(f"schema reader already registered: {key}")
        self._readers[key] = reader

    def read(self, payload: dict[str, Any]) -> dict[str, Any]:
        header = validate_header(payload)
        reader = self._readers.get((header.record_type, header.schema_version))
        if reader is None:
            raise UnsupportedSchemaError(f"unsupported schema: {header.record_type} v{header.schema_version}")
        return reader(dict(payload))

    def supported(self) -> tuple[tuple[str, int], ...]:
        return tuple(sorted(self._readers))
