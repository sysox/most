"""Opt-in live tests for the provider routes documented by MOST.

The tests are intentionally disabled during the normal unit-test run. Enable
all provider checks with ``MOST_RUN_PROVIDER_INTEGRATION=1`` or select one
with ``MOST_PROVIDER=ollama|einfra|claude|codex|gemini|agy``. Provider-specific model variables
are documented in ``ai-catalog.yaml`` and ``install.md``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pytest

from most.cli_chat import ProviderCLIAdapter
from most.http_transport import urllib_json_transport
from most.openai_api import OpenAIAPIAdapter
from most.openai_api import normalize_response as normalize_openai_response
from most.openai_compatible import (
    HTTPResponse,
    OpenAICompatibleAdapter,
    normalize_response,
)

PROMPT = "Reply with exactly: MOST provider smoke test works"


@dataclass(frozen=True)
class Provider:
    name: str
    adapter: object
    configuration: dict[str, object]
    credential: str | None = None
    response_kind: str = "http"


def _providers() -> list[Provider]:
    selected_model = os.environ.get("MOST_MODEL")
    return [
        Provider(
            "ollama",
            OpenAICompatibleAdapter(urllib_json_transport),
            {
                "model_reference": selected_model or os.environ.get("MOST_OLLAMA_MODEL", "granite4.1:3b"),
                "adapter_options": {
                    "base_url": os.environ.get(
                        "MOST_OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1"
                    )
                },
            },
        ),
        Provider(
            "einfra",
            OpenAICompatibleAdapter(urllib_json_transport),
            {
                "model_reference": selected_model or os.environ.get("MOST_EINFRA_MODEL", "mini"),
                "adapter_options": {
                    "base_url": os.environ.get(
                        "MOST_EINFRA_BASE_URL", "https://llm.ai.e-infra.cz/v1"
                    )
                },
            },
            os.environ.get("CERIT_API_KEY"),
        ),
        Provider(
            "openai",
            OpenAIAPIAdapter(urllib_json_transport),
            {
                "model_reference": selected_model or os.environ.get("MOST_OPENAI_MODEL", "gpt-5.6"),
                "adapter_options": {
                    "base_url": os.environ.get("MOST_OPENAI_BASE_URL", "https://api.openai.com/v1")
                },
            },
            os.environ.get("OPENAI_API_KEY"),
            response_kind="responses",
        ),
        *[
            Provider(
                provider,
                ProviderCLIAdapter(provider, Path.cwd()),
                {"adapter_options": {"executable": provider}},
                response_kind="cli",
            )
            for provider in ("claude", "codex", "gemini", "agy")
        ],
    ]


def _skip_reason(provider: Provider) -> str | None:
    if not os.environ.get("MOST_RUN_PROVIDER_INTEGRATION"):
        return "set MOST_RUN_PROVIDER_INTEGRATION=1 to run provider smoke tests"
    if provider.name == "einfra" and not provider.credential:
        variable = "CERIT_API_KEY"
        return f"missing provider credential ({variable})"
    if provider.name == "openai" and not provider.credential:
        return "missing provider credential (OPENAI_API_KEY)"
    return None


def _is_selected(provider: Provider) -> bool:
    selected = os.environ.get("MOST_PROVIDER")
    return selected in {None, "all", provider.name}


@pytest.mark.parametrize("provider", _providers(), ids=lambda provider: provider.name)
def test_provider_can_return_assistant_text(provider: Provider):
    if not _is_selected(provider):
        pytest.skip(f"provider not selected by MOST_PROVIDER={os.environ['MOST_PROVIDER']}")
    reason = _skip_reason(provider)
    if reason:
        if os.environ.get("MOST_RUN_PROVIDER_INTEGRATION"):
            pytest.fail(reason)
        pytest.skip(reason)

    request = {"messages": [{"role": "user", "content": PROMPT}]}
    try:
        response = provider.adapter.execute(request, provider.configuration, provider.credential)
    except (ConnectionError, OSError, TimeoutError) as exc:
        pytest.fail(f"{provider.name} is unavailable: {exc}")

    if provider.response_kind == "cli":
        content = str(response["content"]).strip()
    elif provider.response_kind == "responses":
        assert isinstance(response, HTTPResponse)
        normalized = normalize_openai_response(response)
        content = "".join(str(part.get("text", "")) for part in normalized["content_parts"] if isinstance(part, dict)).strip()
    else:
        assert isinstance(response, HTTPResponse)
        normalized = normalize_response(response)
        content = "".join(
            str(part.get("text", ""))
            for part in normalized["content_parts"]
            if isinstance(part, dict)
        ).strip()
    assert content, f"{provider.name} returned no assistant text"
