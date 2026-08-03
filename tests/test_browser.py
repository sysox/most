from pathlib import Path

import pytest

from most.browser import BrowserProfileIsolationError, IsolatedBrowserProfileService
from most.cli import build_parser


def test_browser_profile_must_be_managed_and_non_overlapping(tmp_path: Path):
    service = IsolatedBrowserProfileService(tmp_path / "profiles")
    assert service.validate_isolated_profile_path(tmp_path / "profiles" / "p1", [tmp_path / "journal"]).name == "p1"
    with pytest.raises(BrowserProfileIsolationError):
        service.validate_isolated_profile_path(tmp_path / "journal" / "profile", [tmp_path / "journal"])


def test_browser_chat_parser_requires_supported_provider():
    args = build_parser().parse_args(["browser-chat", "gemini", "hello"])
    assert args.provider == "gemini"
    assert args.prompt == "hello"


def test_browser_chat_parser_supports_manual_relay():
    args = build_parser().parse_args(["browser-chat", "chatgpt", "--manual"])
    assert args.manual is True
