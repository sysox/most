"""Generic official-cloud API adapter boundary.

Provider-specific authentication and response normalization are intentionally
injected; this adapter never silently falls back to another access method.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from .adapters import Connectivity, Observability
from .openai_compatible import HTTPResponse


class CloudAPIAdapter:
    adapter_type = "official-cloud-api"

    def __init__(self, transport: Callable[[str, dict[str, str], dict[str, Any]], HTTPResponse] | None = None):
        self.transport = transport

    def validate_configuration(self, configuration: dict[str, Any]) -> list[str]:
        options = configuration.get("adapter_options", {})
        return [field for field in ("base_url", "api_key_header") if not options.get(field)]

    def get_observability_profile(self, configuration: dict[str, Any]) -> Observability:
        return Observability.STRUCTURED_STREAM

    def resolve_connectivity(self, configuration: dict[str, Any]) -> Connectivity:
        endpoint = configuration.get("adapter_options", {}).get("base_url")
        parsed = urlparse(endpoint or "")
        return Connectivity(endpoint, "provider-cloud", "public-internet", "DECLARED", (f"provider host: {parsed.hostname or 'unknown'}",))

    def execute(self, request: dict[str, Any], configuration: dict[str, Any], credential_handle: str | None = None) -> HTTPResponse:
        errors = self.validate_configuration(configuration)
        if errors:
            raise ValueError("invalid cloud configuration: " + "; ".join(errors))
        if not credential_handle:
            raise PermissionError("cloud execution requires an opaque credential handle")
        if self.transport is None:
            raise RuntimeError("no cloud HTTP transport configured")
        options = configuration["adapter_options"]
        headers = {"content-type": "application/json", options["api_key_header"]: credential_handle}
        return self.transport(options["base_url"], headers, request)
