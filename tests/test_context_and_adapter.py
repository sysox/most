import pytest

from most.context import ContextOverflowError, enforce_budget
from most.openai_compatible import HTTPResponse, OpenAICompatibleAdapter


def test_budget_fails_when_pinned_content_cannot_fit():
    with pytest.raises(ContextOverflowError):
        enforce_budget([{"content": "x" * 100}], token_limit=1, pinned_indices={0})


def test_openai_compatible_adapter_does_not_send_without_transport():
    adapter = OpenAICompatibleAdapter()
    with pytest.raises(RuntimeError):
        adapter.execute({"messages": []}, {"model_reference": "m", "adapter_options": {"base_url": "http://localhost/v1"}})


def test_openai_compatible_adapter_builds_request_with_opaque_credential():
    calls = []
    def transport(url, headers, payload):
        calls.append((url, headers, payload))
        return HTTPResponse(200, {"ok": True})
    adapter = OpenAICompatibleAdapter(transport)
    response = adapter.execute({"messages": [{"role": "user", "content": "hi"}]},
                               {"model_reference": "m", "adapter_options": {"base_url": "http://localhost/v1"}}, "opaque")
    assert response.status == 200
    assert calls[0][1]["authorization"] == "Bearer opaque"


def test_openai_compatible_adapter_keeps_cerit_key_out_of_payload():
    calls = []
    def transport(url, headers, payload):
        calls.append((url, headers, payload))
        return HTTPResponse(200, {"choices": [{"message": {"content": "ok"}}]})
    adapter = OpenAICompatibleAdapter(transport)
    adapter.execute({"messages": [{"role": "user", "content": "hi"}]}, {
        "model_reference": "mini", "adapter_options": {"base_url": "https://llm.ai.e-infra.cz/v1"}
    }, "secret")
    assert calls[0][0] == "https://llm.ai.e-infra.cz/v1/chat/completions"
    assert "secret" not in repr(calls[0][2])


def test_einfra_reasoning_alias_enables_thinking():
    calls = []

    def transport(url, headers, payload):
        calls.append(payload)
        return HTTPResponse(200, {"choices": [{"message": {"content": "ok"}}]})

    OpenAICompatibleAdapter(transport).execute(
        {"messages": [{"role": "user", "content": "hi"}]},
        {"provider_id": "einfra", "model_reference": "deepseek-thinking",
         "adapter_options": {"base_url": "https://llm.ai.e-infra.cz/v1"}},
        "secret",
    )
    assert calls[0]["chat_template_kwargs"] == {"thinking": True}


def test_einfra_glm_can_disable_thinking_without_leaking_internal_option():
    calls = []

    def transport(url, headers, payload):
        calls.append(payload)
        return HTTPResponse(200, {"choices": [{"message": {"content": "ok"}}]})

    OpenAICompatibleAdapter(transport).execute(
        {"messages": [], "generation_options": {"thinking": False}},
        {"provider_id": "einfra", "model_reference": "glm",
         "adapter_options": {"base_url": "https://llm.ai.e-infra.cz/v1"}},
        "secret",
    )
    assert calls[0]["chat_template_kwargs"] == {"enable_thinking": False}
    assert "thinking" not in calls[0]
