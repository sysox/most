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


def test_browser_chat_supports_cerit_webui():
    args = build_parser().parse_args(["browser-chat", "cerit", "hello", "--manual"])
    assert args.provider == "cerit"
