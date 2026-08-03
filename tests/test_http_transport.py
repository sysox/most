import json

from most.http_transport import urllib_json_transport


class Response:
    status = 200
    def read(self):
        return json.dumps({"ok": True}).encode()
    def __enter__(self): return self
    def __exit__(self, *args): return None


def test_urllib_transport_builds_json_post(monkeypatch):
    calls = []
    monkeypatch.setattr("most.http_transport.urlopen", lambda request, timeout: calls.append((request, timeout)) or Response())
    result = urllib_json_transport("http://localhost/api", {"x-test": "1"}, {"hello": "world"}, timeout=2)
    assert result.body == {"ok": True}
    assert calls[0][0].method == "POST"
    assert calls[0][1] == 2
