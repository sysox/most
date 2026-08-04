"""Opt-in smoke test for the provider routes documented by MOST.

The test is intentionally disabled during the normal unit-test run.  Enable it
with ``MOST_RUN_PROVIDER_INTEGRATION=1`` after configuring the provider
credentials described in ``install.md``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import pytest

from most.cloud_adapter import CloudAPIAdapter
from most.http_transport import urllib_json_transport
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


def _providers() -> list[Provider]:
    return [
        Provider(
            "ollama",
            OpenAICompatibleAdapter(urllib_json_transport),
            {
                "model_reference": os.environ.get("MOST_OLLAMA_MODEL", "granite4.1:3b"),
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
                "model_reference": os.environ.get("MOST_EINFRA_MODEL", "mini"),
                "adapter_options": {
                    "base_url": os.environ.get(
                        "MOST_EINFRA_BASE_URL", "https://llm.ai.e-infra.cz/v1"
                    )
                },
            },
            os.environ.get("CERIT_API_KEY"),
        ),
        Provider(
            "cloud",
            CloudAPIAdapter(urllib_json_transport),
            {
                "model_reference": os.environ.get("MOST_CLOUD_MODEL", "gpt-4o-mini"),
                "adapter_options": {
                    "base_url": os.environ.get(
                        "MOST_CLOUD_BASE_URL", "https://api.openai.com/v1/chat/completions"
                    ),
                    "api_key_header": os.environ.get(
                        "MOST_CLOUD_API_KEY_HEADER", "authorization"
                    ),
                }
            },
            os.environ.get("MOST_CLOUD_API_KEY") or os.environ.get("OPENAI_API_KEY"),
        ),
    ]


def _skip_reason(provider: Provider) -> str | None:
    if not os.environ.get("MOST_RUN_PROVIDER_INTEGRATION"):
        return "set MOST_RUN_PROVIDER_INTEGRATION=1 to run provider smoke tests"
    if provider.name in {"einfra", "cloud"} and not provider.credential:
        variable = "CERIT_API_KEY" if provider.name == "einfra" else "MOST_CLOUD_API_KEY or OPENAI_API_KEY"
        return f"missing provider credential ({variable})"
    return None


@pytest.mark.parametrize("provider", _providers(), ids=lambda provider: provider.name)
def test_provider_can_return_assistant_text(provider: Provider):
    reason = _skip_reason(provider)
    if reason:
        pytest.skip(reason)

    request = {"messages": [{"role": "user", "content": PROMPT}]}
    if provider.name == "cloud":
        request["model"] = provider.configuration["model_reference"]
    try:
        response = provider.adapter.execute(request, provider.configuration, provider.credential)
    except (ConnectionError, OSError, TimeoutError) as exc:
        pytest.skip(f"{provider.name} is unavailable: {exc}")

    assert isinstance(response, HTTPResponse)
    normalized = normalize_response(response)
    content = "".join(
        str(part.get("text", ""))
        for part in normalized["content_parts"]
        if isinstance(part, dict)
    ).strip()
    assert content, f"{provider.name} returned no assistant text"
