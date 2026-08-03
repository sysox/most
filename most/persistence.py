"""Crash-safe file persistence primitives."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable

import yaml


class PersistenceError(RuntimeError):
    pass


class PersistenceCoordinator:
    """Single-writer coordinator for one application-data root."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

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
            os.replace(temporary, target)
        except Exception:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise
        return target

    def _target(self, relative: str) -> Path:
        target = (self.root / relative).resolve()
        root = self.root.resolve()
        if target != root and root not in target.parents:
            raise ValueError("persistence path escapes application-data root")
        return target
