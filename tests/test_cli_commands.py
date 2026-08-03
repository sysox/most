import json
from argparse import Namespace
from pathlib import Path

from most.cli import main
from most.openai_compatible import HTTPResponse


class FakeAdapter:
    def validate_configuration(self, configuration):
        return []

    def resolve_connectivity(self, configuration):
        from most.adapters import Connectivity
        return Connectivity("http://127.0.0.1:11434/v1", "local", "localhost", "DECLARED")

    def get_observability_profile(self, configuration):
        from most.adapters import Observability
        return Observability.STRUCTURED_STREAM

    def execute(self, request, configuration, credential_handle):
        return HTTPResponse(200, {"choices": [{"message": {"content": "local reply"}, "finish_reason": "stop"}]})


class FakeRegistry:
    def get(self, adapter_type):
        return FakeAdapter()


def test_cli_lists_created_sessions(tmp_path: Path, capsys):
    assert main(["--data-root", str(tmp_path), "create-session", "demo"]) == 0
    capsys.readouterr()
    assert main(["--data-root", str(tmp_path), "list-sessions"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output[0]["title"] == "demo"


def test_cli_chat_persists_local_session_and_result(tmp_path: Path, capsys):
    from most.cli import run_chat

    args = Namespace(
        data_root=tmp_path,
        prompt="hello",
        model="granite4.1:3b",
        base_url="http://127.0.0.1:11434/v1",
        title="local",
    )
    assert run_chat(args, registry=FakeRegistry()) == 0
    output = capsys.readouterr().out
    assert "local reply" in output
    assert list((tmp_path / "sessions").glob("*/results/*.md"))
    assert list((tmp_path / "executions").glob("*/metadata.yaml"))


def test_provider_cli_command_mapping():
    from most.cli_chat import command_for

    assert command_for("codex", "hello")[:5] == ("exec", "--ephemeral", "--sandbox", "read-only", "--skip-git-repo-check")
    assert command_for("claude", "hello") == ("-p", "hello")
    assert command_for("gemini", "hello") == ("-p", "hello")
