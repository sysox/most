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


def normalize_response(response: HTTPResponse) -> dict[str, Any]:
    if response.status >= 400:
        raise RuntimeError(f"provider returned HTTP {response.status}")
    body = response.body
    choices = body.get("choices")
    if not isinstance(choices, list):
        raise TypeError("provider response does not contain choices")
    return {
        "content_parts": [{"type": "text", "text": choice.get("message", {}).get("content", "")} for choice in choices],
        "finish_status": choices[0].get("finish_reason") if choices else None,
        "usage": body.get("usage", {}),
        "provider_metadata": {key: value for key, value in body.items() if key not in {"choices", "usage"}},
    }


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

    def execute(self, request: dict[str, Any], configuration: dict[str, Any], credential: str | None = None) -> HTTPResponse:
        if self.transport is None:
            raise RuntimeError("no HTTP transport configured")
        errors = self.validate_configuration(configuration)
        if errors:
            raise ValueError("invalid configuration: " + "; ".join(errors))
        options = configuration["adapter_options"]
        headers = {"content-type": "application/json"}
        if credential:
            headers["authorization"] = f"Bearer {credential}"
        model = str(configuration["model_reference"])
        payload: dict[str, Any] = {
            "model": model,
            "messages": request.get("messages", []),
        }
        generation_options = request.get("generation_options", {})
        if isinstance(generation_options, dict):
            payload.update(generation_options)
        if configuration.get("provider_id") == "einfra":
            payload = _apply_einfra_reasoning_mode(payload, model)
        return self.transport(options["base_url"].rstrip("/") + "/chat/completions", headers, payload)

    def stream(self, request: dict[str, Any], configuration: dict[str, Any], credential: str | None = None):
        """Yield provider-supplied stream records without fabricating hidden steps."""
        response = self.execute({**request, "stream": True}, configuration, credential)
        events = response.body.get("events", [])
        if not isinstance(events, list):
            raise TypeError("stream transport must return an events list")
        for event in events:
            if isinstance(event, dict):
                yield event


def _apply_einfra_reasoning_mode(payload: dict[str, Any], model: str) -> dict[str, Any]:
    """Translate the neutral MOST thinking option to e-INFRA template kwargs."""
    options = payload.pop("thinking", None)
    if options is None and model in {"thinker", "deepseek-thinking"}:
        options = True
    if options is None:
        return payload
    if not isinstance(options, bool):
        raise TypeError("thinking option must be boolean")
    kwargs = dict(payload.get("chat_template_kwargs", {}))
    if model.startswith("glm"):
        kwargs["enable_thinking"] = options
    elif model.startswith("deepseek") or model in {"thinker", "deepseek-thinking"}:
        kwargs["thinking"] = options
    else:
        raise ValueError(f"thinking mode is not supported for e-INFRA model: {model}")
    payload["chat_template_kwargs"] = kwargs
    return payload
