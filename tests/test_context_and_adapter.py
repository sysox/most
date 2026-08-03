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
