"""Minimal OpenAI-compatible adapter boundary.

The transport is injected so production code can use urllib/httpx while tests can
prove request construction without sending data to a provider.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from .adapters import Connectivity, Observability


@dataclass(frozen=True, slots=True)
class HTTPResponse:
    status: int
    body: dict[str, Any]


class OpenAICompatibleAdapter:
    adapter_type = "openai-compatible"

    def __init__(self, transport: Callable[[str, dict[str, str], dict[str, Any]], HTTPResponse] | None = None):
        self.transport = transport

    def validate_configuration(self, configuration: dict[str, Any]) -> list[str]:
        options = configuration.get("adapter_options", {})
        errors: list[str] = []
        if not options.get("base_url"):
            errors.append("adapter_options.base_url is required")
        if not configuration.get("model_reference"):
            errors.append("model_reference is required")
        return errors

    def resolve_connectivity(self, configuration: dict[str, Any]) -> Connectivity:
        endpoint = configuration.get("adapter_options", {}).get("base_url")
        parsed = urlparse(endpoint or "")
        host = parsed.hostname or ""
        if host in {"localhost", "127.0.0.1", "::1"}:
            location, network, confidence = "local", "localhost", "DECLARED"
        elif host.startswith(("10.", "192.168.", "172.")):
            location, network, confidence = "remote-private", "local-network", "DECLARED"
        else:
            location, network, confidence = configuration.get("location", "remote-public"), configuration.get("network"), "DECLARED"
        return Connectivity(endpoint, location, network, confidence, ("endpoint configuration",))

    def get_observability_profile(self, configuration: dict[str, Any]) -> Observability:
        return Observability.STRUCTURED_STREAM

    def execute(self, request: dict[str, Any], configuration: dict[str, Any], credential_handle: str | None = None) -> HTTPResponse:
        if self.transport is None:
            raise RuntimeError("no HTTP transport configured")
        errors = self.validate_configuration(configuration)
        if errors:
            raise ValueError("invalid configuration: " + "; ".join(errors))
        options = configuration["adapter_options"]
        headers = {"content-type": "application/json"}
        if credential_handle:
            headers["authorization"] = f"Bearer {credential_handle}"
        payload = {**request, "model": configuration["model_reference"]}
        return self.transport(options["base_url"].rstrip("/") + "/chat/completions", headers, payload)
