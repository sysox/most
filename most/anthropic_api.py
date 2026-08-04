"""Anthropic Messages API adapter."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from .adapters import Connectivity, Observability
from .openai_compatible import HTTPResponse


def normalize_response(response: HTTPResponse) -> dict[str, Any]:
    if response.status >= 400:
        error = response.body.get("error", response.body)
        raise RuntimeError(f"Anthropic returned HTTP {response.status}: {error}")
    parts = [
        {"type": "text", "text": block["text"]}
        for block in response.body.get("content", [])
        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)
    ]
    return {
        "content_parts": parts,
        "finish_status": response.body.get("stop_reason"),
        "usage": response.body.get("usage", {}),
        "provider_metadata": {key: value for key, value in response.body.items() if key not in {"content", "usage"}},
    }


class AnthropicAPIAdapter:
    adapter_type = "anthropic-api"

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
        host = urlparse(endpoint or "").hostname or "unknown"
        return Connectivity(endpoint, "provider-cloud", "public-internet", "DECLARED", (f"provider host: {host}",))

    def get_observability_profile(self, configuration: dict[str, Any]) -> Observability:
        return Observability.STRUCTURED_STREAM

    def execute(self, request: dict[str, Any], configuration: dict[str, Any], credential: str | None = None) -> HTTPResponse:
        errors = self.validate_configuration(configuration)
        if errors:
            raise ValueError("invalid Anthropic configuration: " + "; ".join(errors))
        if not credential:
            raise PermissionError("Anthropic execution requires a credential")
        if self.transport is None:
            raise RuntimeError("no HTTP transport configured")
        messages = []
        system_parts = []
        for message in request.get("messages", []):
            if not isinstance(message, dict):
                continue
            role = str(message.get("role", "user"))
            content = message.get("content", "")
            if role == "system":
                system_parts.append(str(content))
            else:
                messages.append({"role": "assistant" if role == "assistant" else "user", "content": content})
        payload: dict[str, Any] = {
            "model": configuration["model_reference"],
            "messages": messages,
            "max_tokens": 1024,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        headers = {
            "content-type": "application/json",
            "x-api-key": credential,
            "anthropic-version": "2023-06-01",
        }
        return self.transport(configuration["adapter_options"]["base_url"].rstrip("/") + "/v1/messages", headers, payload)
