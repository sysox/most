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


class IndexService:
    """Rebuildable indexes; authoritative records remain in their source files."""

    def __init__(self, store: PersistenceCoordinator):
        self.store = store

    def rebuild_yaml_index(self, source_directory: str, index_name: str) -> Path:
        source = self.store.root / source_directory
        entries: list[dict[str, Any]] = []
        for path in sorted(source.glob("*.yaml")):
            value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(value, dict):
                entries.append({"record_id": value.get("record_id", path.stem), "path": str(path.relative_to(self.store.root))})
        return self.store.write_json(f"indexes/{index_name}.json", {"source": source_directory, "entries": entries})
