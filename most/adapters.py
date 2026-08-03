"""Adapter boundary with conservative observability defaults."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol


class Observability(str, Enum):
    GRANULAR = "GRANULAR"
    STRUCTURED_STREAM = "STRUCTURED_STREAM"
    TEXT_STREAM = "TEXT_STREAM"
    BLOCK = "BLOCK"
    OPAQUE = "OPAQUE"


@dataclass(frozen=True, slots=True)
class Connectivity:
    endpoint: str | None
    location: str
    network: str | None
    confidence: str
    evidence: tuple[str, ...] = ()


class Adapter(Protocol):
    def validate_configuration(self, configuration: dict[str, Any]) -> list[str]: ...
    def resolve_connectivity(self, configuration: dict[str, Any]) -> Connectivity: ...
    def get_observability_profile(self, configuration: dict[str, Any]) -> Observability: ...


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, Adapter] = {}

    def register(self, adapter_type: str, adapter: Adapter) -> None:
        if adapter_type in self._adapters:
            raise ValueError(f"adapter already registered: {adapter_type}")
        self._adapters[adapter_type] = adapter

    def get(self, adapter_type: str) -> Adapter:
        try:
            return self._adapters[adapter_type]
        except KeyError as exc:
            raise KeyError(f"unknown adapter: {adapter_type}") from exc

    def types(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))
