from pathlib import Path

import pytest

from most.browser import BrowserAdapter, IsolatedBrowserProfileService, SelectorPack
from most.openai_compatible import HTTPResponse, normalize_response


class Driver:
    def __init__(self):
        self.calls = []
    def click(self, selector): self.calls.append(("click", selector))
    def type_text(self, selector, value): self.calls.append(("type", selector, value))
    def read_text(self, selector): return "answer"
    def screenshot(self): return "screenshot-ref"
    def sanitized_dom(self): return "dom-ref"


def test_browser_adapter_uses_versioned_selector_pack(tmp_path: Path):
    profile = IsolatedBrowserProfileService(tmp_path / "profiles")
    adapter = BrowserAdapter(profile, {"provider": SelectorPack("provider", "1", {"input": "#input", "submit": "#submit", "output": "#output"})})
    result = adapter.execute({"provider_id": "provider", "prompt": "hi"}, Driver())
    assert result == {"text": "answer", "selector_pack_version": "1"}


def test_response_normalization_rejects_provider_error():
    with pytest.raises(RuntimeError):
        normalize_response(HTTPResponse(500, {}))
