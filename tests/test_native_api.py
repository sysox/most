from most.anthropic_api import AnthropicAPIAdapter
from most.anthropic_api import normalize_response as normalize_anthropic
from most.gemini_api import GeminiAPIAdapter
from most.gemini_api import normalize_response as normalize_gemini
from most.openai_compatible import HTTPResponse


def test_anthropic_adapter_builds_messages_request_without_persistence_fields():
    calls = []

    def transport(url, headers, payload):
        calls.append((url, headers, payload))
        return HTTPResponse(200, {"content": [{"type": "text", "text": "hello"}], "stop_reason": "end_turn"})

    adapter = AnthropicAPIAdapter(transport)
    response = adapter.execute(
        {"schema_version": 1, "messages": [{"role": "user", "content": "hi"}]},
        {"model_reference": "claude-sonnet-5", "adapter_options": {"base_url": "https://api.anthropic.com"}},
        "secret",
    )
    assert calls[0][0].endswith("/v1/messages")
    assert calls[0][1]["x-api-key"] == "secret"
    assert "secret" not in repr(calls[0][2])
    assert "schema_version" not in calls[0][2]
    assert normalize_anthropic(response)["content_parts"] == [{"type": "text", "text": "hello"}]


def test_gemini_adapter_builds_generate_content_request():
    calls = []

    def transport(url, headers, payload):
        calls.append((url, headers, payload))
        return HTTPResponse(200, {
            "candidates": [{"content": {"parts": [{"text": "hello"}]}, "finishReason": "STOP"}],
        })

    adapter = GeminiAPIAdapter(transport)
    response = adapter.execute(
        {"messages": [{"role": "user", "content": "hi"}]},
        {"model_reference": "models/gemini-3.5-flash", "adapter_options": {"base_url": "https://generativelanguage.googleapis.com/v1beta"}},
        "secret",
    )
    assert calls[0][0].endswith("/models/gemini-3.5-flash:generateContent")
    assert calls[0][1]["x-goog-api-key"] == "secret"
    assert normalize_gemini(response)["content_parts"] == [{"type": "text", "text": "hello"}]
