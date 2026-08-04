from most.openai_api import OpenAIAPIAdapter, normalize_response
from most.openai_compatible import HTTPResponse


def test_openai_responses_are_normalized():
    result = normalize_response(HTTPResponse(200, {
        "status": "completed",
        "output": [{"type": "message", "content": [{"type": "output_text", "text": "hello"}]}],
        "usage": {"total_tokens": 3},
    }))
    assert result["content_parts"] == [{"type": "text", "text": "hello"}]
    assert result["finish_status"] == "completed"


def test_openai_adapter_posts_to_responses_without_leaking_key():
    calls = []

    def transport(url, headers, payload):
        calls.append((url, headers, payload))
        return HTTPResponse(200, {"output_text": "ok"})

    adapter = OpenAIAPIAdapter(transport)
    adapter.execute({"messages": [{"role": "user", "content": "hi"}]}, {
        "model_reference": "gpt-5.6",
        "adapter_options": {"base_url": "https://api.openai.com/v1"},
    }, "secret")
    assert calls[0][0] == "https://api.openai.com/v1/responses"
    assert calls[0][1]["authorization"] == "Bearer secret"
    assert "secret" not in repr(calls[0][2])
    assert calls[0][2]["model"] == "gpt-5.6"
    assert "schema_version" not in calls[0][2]
