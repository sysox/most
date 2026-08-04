"""Google Gemini generateContent API adapter."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from .adapters import Connectivity, Observability
from .openai_compatible import HTTPResponse


def normalize_response(response: HTTPResponse) -> dict[str, Any]:
    if response.status >= 400:
        error = response.body.get("error", response.body)
        raise RuntimeError(f"Google Gemini returned HTTP {response.status}: {error}")
    parts: list[dict[str, str]] = []
    candidates = response.body.get("candidates", [])
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content", {})
        for part in content.get("parts", []) if isinstance(content, dict) else []:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append({"type": "text", "text": part["text"]})
    return {
        "content_parts": parts,
        "finish_status": candidates[0].get("finishReason") if candidates and isinstance(candidates[0], dict) else None,
        "usage": response.body.get("usageMetadata", {}),
        "provider_metadata": {key: value for key, value in response.body.items() if key not in {"candidates", "usageMetadata"}},
    }


class GeminiAPIAdapter:
    adapter_type = "gemini-api"

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
            raise ValueError("invalid Gemini configuration: " + "; ".join(errors))
        if not credential:
            raise PermissionError("Gemini execution requires a credential")
        if self.transport is None:
            raise RuntimeError("no HTTP transport configured")
        contents = []
        for message in request.get("messages", []):
            if not isinstance(message, dict):
                continue
            role = "model" if message.get("role") == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": str(message.get("content", ""))}]})
        payload = {
            "contents": contents,
            "generationConfig": {"maxOutputTokens": 1024},
        }
        model = str(configuration["model_reference"]).removeprefix("models/")
        url = configuration["adapter_options"]["base_url"].rstrip("/") + f"/models/{model}:generateContent"
        headers = {"content-type": "application/json", "x-goog-api-key": credential}
        return self.transport(url, headers, payload)
