import json
from argparse import Namespace
from pathlib import Path

import pytest

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
    from most.cli_chat import (
        command_for,
        credential_environment,
        mcp_config_payload,
        opencode_config_payload,
    )

    assert command_for("codex", "hello")[:5] == ("exec", "--ephemeral", "--sandbox", "read-only", "--skip-git-repo-check")
    assert command_for("claude", "hello") == ("-p", "hello")
    assert command_for("gemini", "hello") == ("-p", "hello")
    assert command_for("agy", "hello") == ("--output-format", "text", "--sandbox", "--print", "hello")
    assert command_for("opencode", "hello") == ("run", "hello")
    assert command_for("codex", "hello", writable=True) == ("exec", "--sandbox", "workspace-write", "--skip-git-repo-check", "hello")
    assert command_for("claude", "hello", writable=True) == ("-p", "--permission-mode", "acceptEdits", "hello")
    with pytest.raises(ValueError, match="writable mode"):
        command_for("gemini", "hello", writable=True)
    environment, variable = credential_environment("claude", "einfra", "agentic")
    assert environment["ANTHROPIC_BASE_URL"] == "https://llm.ai.e-infra.cz/"
    assert environment["ANTHROPIC_MODEL"] == "agentic"
    assert variable == "ANTHROPIC_AUTH_TOKEN"
    environment, variable = credential_environment("opencode", "einfra", "mini")
    assert environment["OPENAI_BASE_URL"].endswith("/v1")
    assert variable == "OPENAI_API_KEY"
    payload = mcp_config_payload(["ddg_search"])
    assert payload["mcpServers"]["ddg_search"]["url"].endswith("/ddg_search/mcp")
    assert "${MOST_MCP_AUTH}" in str(payload)
    with pytest.raises(ValueError, match="unknown e-INFRA MCP"):
        mcp_config_payload(["missing"])
    config = opencode_config_payload("mini", ["ddg_search"])
    assert config["model"] == "einfra/mini"
    assert config["mcp"]["ddg_search"]["headers"]["Authorization"] == "Bearer {env:MOST_MCP_AUTH}"


def test_cli_chat_sensitive_einfra_guard_uses_catalog():
    from most.cli_chat import _enforce_einfra_model_sensitivity

    _enforce_einfra_model_sensitivity("mini", "sensitive", Path("ai-catalog.yaml"))
    with pytest.raises(SystemExit, match="model not found in catalog"):
        _enforce_einfra_model_sensitivity("unknown-model", "sensitive", Path("ai-catalog.yaml"))


def test_cerit_chat_sensitive_guard_accepts_legacy_namespace_without_catalog():
    from most.cli import _enforce_einfra_model_sensitivity

    _enforce_einfra_model_sensitivity("mini", "sensitive", Path("ai-catalog.yaml"))


def test_multimodal_cli_tasks_create_execution_and_exposure_record(tmp_path: Path, monkeypatch, capsys):
    from most import cli
    from most.adapters import Connectivity
    from most.multimodal_adapter import MultimodalResult

    class FakeMultimodalAdapter:
        def validate_configuration(self, configuration):
            return []

        def resolve_connectivity(self, configuration):
            return Connectivity("http://127.0.0.1:11434/v1", "local", "localhost", "DECLARED")

        def get_observability_profile(self, configuration):
            return "STRUCTURED_STREAM"

        def execute(self, request, configuration, credential):
            operation = configuration["adapter_options"]["operation"]
            if operation == "embedding":
                return MultimodalResult([0.1, 0.2], {"operation": operation, "dimensions": 2})
            if operation == "image-analysis":
                return MultimodalResult("looks good", {"operation": operation})
            if operation == "transcription":
                return MultimodalResult("spoken text", {"operation": operation})
            return MultimodalResult(b"binary", {"operation": operation, "mime_type": "audio/wav"})

    monkeypatch.setattr("most.multimodal_adapter.MultimodalAdapter", FakeMultimodalAdapter)
    option = {
        "access_method": "openai-compatible", "endpoint": "http://127.0.0.1:11434/v1",
        "adapter_type": "openai-compatible", "credential_env": None, "pricing": {},
    }
    monkeypatch.setattr(cli, "_select_capability_task", lambda args: (option, None))
    input_path = tmp_path / "input.txt"
    input_path.write_text("hello", encoding="utf-8")
    image_path = tmp_path / "input.png"
    image_path.write_bytes(b"png")
    audio_path = tmp_path / "input.wav"
    audio_path.write_bytes(b"wav")

    common = {"data_root": tmp_path, "provider": "ollama", "model": "test-model", "catalog": Path("ai-catalog.yaml"),
              "discovered": Path("ai-discovered.yaml"), "no_refresh": True, "max_age_hours": 24.0}
    cli.run_embedding(Namespace(**common, input=input_path, output=tmp_path / "embedding.json", required_capability="embedding", required_output_modality="embedding", required_input_modality=None))
    cli.run_image_generation(Namespace(**common, prompt="draw", output=tmp_path / "image.bin", required_capability="image", required_output_modality="image", required_input_modality=None))
    cli.run_speech(Namespace(**common, text="speak", output=tmp_path / "speech.bin", required_capability="speech", required_output_modality="audio", required_input_modality=None))
    cli.run_image_analysis(Namespace(**common, input=image_path, prompt="describe", required_capability="chat", required_output_modality=None, required_input_modality="image"))
    cli.run_transcription(Namespace(**common, input=audio_path, required_capability="transcription", required_output_modality="text", required_input_modality="audio", require_credential=False))
    capsys.readouterr()
    metadata = list((tmp_path / "executions").glob("*/metadata.yaml"))
    assert len(metadata) == 5
    assert all("resolved_connectivity" in path.read_text(encoding="utf-8") for path in metadata)


def test_transcription_requires_credentials_for_remote_providers():
    from most.cli import build_parser

    args = build_parser().parse_args([
        "ai-transcribe", "--provider", "einfra", "--model", "whisper-large-v3", "--input", "audio.wav",
    ])

    assert getattr(args, "require_credential", True) is True
