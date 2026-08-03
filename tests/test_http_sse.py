import json

from most.http_transport import urllib_json_transport


class Headers:
    def get_content_type(self): return "text/event-stream"


class StreamResponse:
    status = 200
    headers = Headers()
    def __iter__(self):
        return iter([
            b"data: " + json.dumps({"event_type": "TextDeltaEvent", "delta": "hi"}).encode() + b"\n",
            b"data: [DONE]\n",
        ])
    def __enter__(self): return self
    def __exit__(self, *args): return None


def test_transport_parses_sse_until_done(monkeypatch):
    monkeypatch.setattr("most.http_transport.urlopen", lambda request, timeout: StreamResponse())
    response = urllib_json_transport("http://localhost/api", {}, {})
    assert response.body["events"][0]["delta"] == "hi"
