"""File-backed record repositories with immutable result content."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic, TypeVar

import yaml

from .persistence import PersistenceCoordinator


T = TypeVar("T")


@dataclass(slots=True)
class RawYamlRepository(Generic[T]):
    store: PersistenceCoordinator
    directory: str

    def save(self, record_id: str, payload: dict[str, Any]) -> Path:
        return self.store.write_yaml(f"{self.directory}/{record_id}.yaml", payload)

    def get(self, record_id: str) -> dict[str, Any] | None:
        path = self.store.root / self.directory / f"{record_id}.yaml"
        if not path.exists():
            return None
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None

    def list(self) -> list[dict[str, Any]]:
        directory = self.store.root / self.directory
        return [yaml.safe_load(path.read_text(encoding="utf-8")) for path in sorted(directory.glob("*.yaml"))]
