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
class CapabilitySet:
    values: frozenset[str] = frozenset()

    def contains(self, capability: str) -> bool:
        return capability in self.values


@dataclass(frozen=True, slots=True)
class EffectiveCapabilities:
    values: frozenset[str]
    restrictions_applied: frozenset[str] = frozenset()


def compute_effective_capabilities(declared: CapabilitySet, discovered: CapabilitySet | None = None,
                                   restrictions: CapabilitySet | None = None) -> EffectiveCapabilities:
    available = discovered.values if discovered and discovered.values else declared.values
    blocked = restrictions.values if restrictions else frozenset()
    return EffectiveCapabilities(frozenset(available - blocked), frozenset(blocked))


@dataclass(frozen=True, slots=True)
class Connectivity:
    endpoint: str | None
    location: str
    network: str | None
    confidence: str
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AdapterExecutionContext:
    execution_id: str
    request_snapshot: dict[str, Any]
    configuration_snapshot: dict[str, Any]
    effective_capabilities: EffectiveCapabilities
    context_assembly_record: dict[str, Any]
    resolved_connectivity: Connectivity
    credential_handle: str | None
    workspace_scope: tuple[str, ...]
    cancellation_handle: Any = None
    event_sink: Any = None
    platform_services: Any = None


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

    def validate_configuration(self, adapter_type: str, configuration: dict[str, Any]) -> list[str]:
        return self.get(adapter_type).validate_configuration(configuration)

    def get_observability_profile(self, adapter_type: str, configuration: dict[str, Any]) -> Observability:
        return self.get(adapter_type).get_observability_profile(configuration)
