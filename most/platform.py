"""Platform-neutral service protocols used by adapters and orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class SecretStore(Protocol):
    def resolve(self, reference): ...


class PathService(Protocol):
    def application_data_root(self) -> Path: ...


class ProcessService(Protocol):
    def terminate_process_tree(self, process_id: int, grace_seconds: float) -> object: ...


class BrowserProfileService(Protocol):
    def validate_isolated_profile_path(self, profile: Path, forbidden_roots: list[Path]) -> Path: ...


class NetworkInspector(Protocol):
    def inspect(self, endpoint: str, declared_location: str, declared_network: str | None = None): ...
