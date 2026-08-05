import json
from pathlib import Path

import pytest

from most.browser import BrowserProfileIsolationError, IsolatedBrowserProfileService
from most.browser_chat import LOGIN_SELECTORS, SELECTOR_PACKS
from most.browser_selenium import _firefox_binary
from most.cli import build_parser


def test_browser_profile_must_be_managed_and_non_overlapping(tmp_path: Path):
    service = IsolatedBrowserProfileService(tmp_path / "profiles")
    assert service.validate_isolated_profile_path(tmp_path / "profiles" / "p1", [tmp_path / "journal"]).name == "p1"
    with pytest.raises(BrowserProfileIsolationError):
        service.validate_isolated_profile_path(tmp_path / "journal" / "profile", [tmp_path / "journal"])


def test_firefox_binary_skips_shell_launcher_and_finds_real_binary(tmp_path: Path, monkeypatch):
    launcher = tmp_path / "firefox"
    launcher.write_text("#!/bin/sh\nexec firefox-real\n", encoding="utf-8")
    launcher.chmod(0o755)
    real = tmp_path / "firefox-real"
    real.write_bytes(b"\x7fELF")
    real.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("MOST_FIREFOX_BINARY", str(real))
    assert _firefox_binary() == str(real)


def test_browser_chat_parser_requires_supported_provider():
    args = build_parser().parse_args(["browser-chat", "gemini", "hello"])
    assert args.provider == "gemini"
    assert args.prompt == "hello"
    assert SELECTOR_PACKS["gemini"].selectors["input"] == "rich-textarea .ql-editor"
    assert LOGIN_SELECTORS["gemini"] == "button[aria-label='Sign in']"


def test_browser_chat_parser_supports_manual_relay():
    args = build_parser().parse_args(["browser-chat", "chatgpt", "--manual"])
    assert args.manual is True


def test_browser_chat_parser_supports_named_login_profile():
    args = build_parser().parse_args(["browser-chat", "gemini", "--profile", "gemini-edu"])
    assert args.profile == "gemini-edu"


def test_browser_chat_parser_supports_sensitivity_tier():
    args = build_parser().parse_args(["browser-chat", "cerit", "--sensitivity-tier", "sensitive"])
    assert args.sensitivity_tier == "sensitive"


def test_ai_chat_parser_supports_sensitivity_tier():
    args = build_parser().parse_args(["ai-chat", "--model", "mini", "--sensitivity-tier", "sensitive"])
    assert args.sensitivity_tier == "sensitive"


def test_cerit_chat_parser_supports_sensitivity_tier():
    args = build_parser().parse_args(["cerit-chat", "--model", "mini", "--sensitivity-tier", "sensitive"])
    assert args.sensitivity_tier == "sensitive"


def test_policy_check_is_standalone_and_structured(capsys):
    from most.cli import main

    assert main([
        "policy-check", "--sensitivity-tier", "sensitive", "--route", "browser-chat", "--provider", "gemini",
    ]) == 1
    output = json.loads(capsys.readouterr().out)
    assert output["allowed"] is False
    assert output["reason"] == "browser-chat is not allowed for sensitive workloads"


def test_policy_check_rejects_unverified_einfra_model(capsys):
    from most.cli import main

    assert main([
        "policy-check", "--sensitivity-tier", "sensitive", "--route", "ai-chat",
        "--provider", "einfra", "--model", "not-in-catalog",
    ]) == 1
    output = json.loads(capsys.readouterr().out)
    assert output["allowed"] is False
    assert "not eligible" in output["reason"]


def test_tandem_journal_context_flags_are_available_on_cli_commands():
    for command, extra in (
        ("cli-chat", ["codex"]),
        ("ai-chat", []),
        ("cerit-chat", []),
    ):
        arguments = [command, *extra, "--profile", "coding", "--pipeline-id", "pipe-1", "--stage-index", "1"]
        if command in {"ai-chat"}:
            arguments += ["--model", "mini"]
        args = build_parser().parse_args(arguments)
        assert (args.profile, args.pipeline_id, args.stage_index) == ("coding", "pipe-1", 1)


def test_cli_chat_supports_agent_alias():
    args = build_parser().parse_args(["cli-chat", "--agent", "claude", "--writable"])
    assert args.agent == "claude"
    assert args.provider is None


def test_direct_cerit_chat_sensitive_guard_uses_catalog():
    from pathlib import Path

    from most.cli import _enforce_einfra_model_sensitivity

    catalog = Path(__file__).parents[1] / "ai-catalog.yaml"
    _enforce_einfra_model_sensitivity("mini", "sensitive", catalog)


def test_browser_chat_supports_cerit_webui():
    args = build_parser().parse_args(["browser-chat", "cerit", "hello", "--manual"])
    assert args.provider == "cerit"
