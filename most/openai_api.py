"""Official OpenAI Responses API adapter.

This adapter intentionally uses the injected standard-library transport so the
API key remains an opaque runtime credential and the core has no SDK dependency.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from .adapters import Connectivity, Observability
from .openai_compatible import HTTPResponse


def normalize_response(response: HTTPResponse) -> dict[str, Any]:
    if response.status >= 400:
        raise RuntimeError(f"OpenAI returned HTTP {response.status}: {response.body.get('error', response.body)}")

    body = response.body
    parts: list[dict[str, str]] = []
    for item in body.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") in {"output_text", "text"}:
                text = content.get("text", "")
                if isinstance(text, str):
                    parts.append({"type": "text", "text": text})

    # output_text is included by the API as a convenient aggregate.
    if not parts and isinstance(body.get("output_text"), str):
        parts = [{"type": "text", "text": body["output_text"]}]
    return {
        "content_parts": parts,
        "finish_status": body.get("status"),
        "usage": body.get("usage", {}),
        "provider_metadata": {key: value for key, value in body.items() if key not in {"output", "output_text", "usage"}},
    }


class OpenAIAPIAdapter:
    adapter_type = "openai-api"

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
            raise ValueError("invalid OpenAI configuration: " + "; ".join(errors))
        if not credential:
            raise PermissionError("OpenAI execution requires a credential")
        if self.transport is None:
            raise RuntimeError("no HTTP transport configured")
        options = configuration["adapter_options"]
        # `request` is a persisted MOST record and contains internal fields such
        # as schema_version, record_id, and session_id. Only forward provider
        # request fields; OpenAI rejects MOST's persistence envelope.
        payload: dict[str, Any] = {
            "model": configuration["model_reference"],
            "input": request.get("messages", []),
        }
        generation_options = request.get("generation_options", {})
        if isinstance(generation_options, dict):
            payload.update(generation_options)
        headers = {"content-type": "application/json", "authorization": f"Bearer {credential}"}
        return self.transport(options["base_url"].rstrip("/") + "/responses", headers, payload)
