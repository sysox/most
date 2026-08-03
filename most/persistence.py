"""Crash-safe file persistence primitives."""

from __future__ import annotations

import json
import os
import socket
import tempfile
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


class PersistenceError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DataRootLease:
    lease_id: str
    process_id: int
    host_identifier: str
    started_at: str
    heartbeat_at: str
    lease_timeout_seconds: int


class PersistenceCoordinator:
    """Single-writer coordinator for one application-data root."""

    def __init__(self, root: Path, *, replace_retries: int = 4, retry_delay_seconds: float = 0.02):
        self.root = Path(root)
        self.replace_retries = replace_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.root.mkdir(parents=True, exist_ok=True)

    def acquire_data_root_lease(self, timeout_seconds: int = 300) -> DataRootLease:
        path = self._target(".data-root.lease.yaml")
        existing = None
        recovered = False
        if path.exists():
            existing = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if self._existing_lease_active(existing):
                raise RuntimeError("application-data root already has an active lease")
            path.unlink()
            recovered = True
        now = _now()
        lease = DataRootLease(os.urandom(16).hex(), os.getpid(), socket.gethostname(), now, now, timeout_seconds)
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                yaml.safe_dump(asdict(lease), handle, sort_keys=False)
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            path.unlink(missing_ok=True)
            raise
        if recovered:
            self.append_versioned_jsonl(
                "diagnostics/lease-events.jsonl",
                [{"event_type": "stale_lease_recovered", "old_lease_id": existing.get("lease_id")}],
                record_type="LEASE_EVENT",
            )
        return lease

    def heartbeat_data_root_lease(self, lease: DataRootLease) -> DataRootLease:
        current = self._read_lease()
        if not current or current.lease_id != lease.lease_id:
            raise RuntimeError("data-root lease ownership mismatch")
        updated = DataRootLease(lease.lease_id, lease.process_id, lease.host_identifier, lease.started_at, _now(), lease.lease_timeout_seconds)
        self.write_yaml(".data-root.lease.yaml", asdict(updated))
        return updated

    def release_data_root_lease(self, lease_id: str) -> None:
        current = self._read_lease()
        if current and current.lease_id != lease_id:
            raise RuntimeError("data-root lease ownership mismatch")
        self._target(".data-root.lease.yaml").unlink(missing_ok=True)

    def write_yaml(self, relative: str, value: dict[str, Any]) -> Path:
        return self._atomic_write(relative, yaml.safe_dump(value, sort_keys=False, allow_unicode=True))

    def write_json(self, relative: str, value: dict[str, Any]) -> Path:
        return self._atomic_write(relative, json.dumps(value, indent=2, sort_keys=False) + "\n")

    def append_jsonl(self, relative: str, records: Iterable[dict[str, Any]]) -> Path:
        target = self._target(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return target

    def append_versioned_jsonl(self, relative: str, records: Iterable[dict[str, Any]], *, record_type: str,
                               application_version: str = "0.1.0") -> Path:
        from .serialization import versioned_payload
        versioned = []
        for record in records:
            record_id = str(record.get("record_id") or record.get("event_id") or record.get("id") or os.urandom(16).hex())
            versioned.append(versioned_payload(record, record_type=record_type, record_id=record_id, application_version=application_version))
        return self.append_jsonl(relative, versioned)

    def read_jsonl(self, relative: str) -> list[dict[str, Any]]:
        target = self._target(relative)
        if not target.exists():
            return []
        records: list[dict[str, Any]] = []
        lines = target.read_text(encoding="utf-8").splitlines()
        for position, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                # A crash may leave one incomplete final line. Earlier corruption
                # is not ignored because it requires explicit recovery.
                if position == len(lines) - 1:
                    break
                raise PersistenceError(f"invalid JSONL record in {target}")
        return records

    def _atomic_write(self, relative: str, content: str) -> Path:
        target = self._target(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            self._replace_with_retry(Path(temporary), target)
        except Exception:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise
        return target

    def _replace_with_retry(self, temporary: Path, target: Path) -> None:
        for attempt in range(self.replace_retries + 1):
            try:
                os.replace(temporary, target)
                return
            except OSError:
                if attempt >= self.replace_retries:
                    raise
                time.sleep(self.retry_delay_seconds * (2 ** attempt))

    def _target(self, relative: str) -> Path:
        target = (self.root / relative).resolve()
        root = self.root.resolve()
        if target != root and root not in target.parents:
            raise ValueError("persistence path escapes application-data root")
        return target

    def _read_lease(self) -> DataRootLease | None:
        path = self._target(".data-root.lease.yaml")
        if not path.exists():
            return None
        values = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return DataRootLease(**values)

    @staticmethod
    def _existing_lease_active(values: dict[str, Any]) -> bool:
        if values.get("host_identifier") != socket.gethostname():
            return True
        try:
            os.kill(int(values["process_id"]), 0)
        except ProcessLookupError:
            return False
        except (PermissionError, KeyError, ValueError):
            return True
        return True


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
