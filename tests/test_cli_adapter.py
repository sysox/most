import sys
from pathlib import Path

from most.cli_adapter import CLIAdapter
from most.cli_chat import ProviderCLIAdapter, rewind_messages


def test_cli_adapter_cancels_process_group(tmp_path: Path):
    adapter = CLIAdapter()
    execution = adapter.start(sys.executable, ["-c", "import time; time.sleep(30)"], tmp_path)
    report = adapter.cancel(execution, grace_seconds=0.01)
    assert report.requested
    assert execution.process.poll() is not None


def test_rewind_messages_removes_complete_exchanges():
    messages = [
        {"role": "user", "content": "one"}, {"role": "assistant", "content": "one reply"},
        {"role": "user", "content": "two"}, {"role": "assistant", "content": "two reply"},
    ]
    assert rewind_messages(messages, 1) == 1
    assert messages == [{"role": "user", "content": "one"}, {"role": "assistant", "content": "one reply"}]


def test_rewind_messages_rejects_more_turns_than_available():
    import pytest

    with pytest.raises(ValueError, match="only 0 available"):
        rewind_messages([], 1)


def test_provider_cli_uses_named_credential_environment(monkeypatch, tmp_path: Path):
    adapter = ProviderCLIAdapter("claude", tmp_path)
    captured = {}

    def fake_execute(request, configuration, credential):
        captured.update(configuration["adapter_options"])
        assert credential == "secret"
        return {"stdout": "ok", "stderr": "", "returncode": 0}

    monkeypatch.setattr(adapter.cli, "execute", fake_execute)
    result = adapter.execute(
        {"messages": [{"role": "user", "content": "hello"}]},
        {"adapter_options": {"environment": {"ANTHROPIC_BASE_URL": "https://example.invalid"},
                              "credential_env_var": "ANTHROPIC_AUTH_TOKEN"}},
        "secret",
    )
    assert result["content"] == "ok"
    assert captured["credential_env_var"] == "ANTHROPIC_AUTH_TOKEN"


def test_provider_cli_removes_temporary_mcp_config(monkeypatch, tmp_path: Path):
    adapter = ProviderCLIAdapter("claude", tmp_path)
    captured = {}

    def fake_execute(request, configuration, credential):
        captured["arguments"] = configuration["adapter_options"]["arguments"]
        config_path = Path(captured["arguments"][-1])
        assert config_path.exists()
        assert "secret" not in config_path.read_text(encoding="utf-8")
        return {"stdout": "ok", "stderr": "", "returncode": 0}

    monkeypatch.setattr(adapter.cli, "execute", fake_execute)
    result = adapter.execute(
        {"messages": [{"role": "user", "content": "hello"}]},
        {"adapter_options": {"mcp_servers": ["ddg_search"]}},
        "secret",
    )
    assert result["content"] == "ok"
    assert not Path(captured["arguments"][-1]).exists()
