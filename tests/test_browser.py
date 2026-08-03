from pathlib import Path

import pytest

from most.browser import BrowserProfileIsolationError, IsolatedBrowserProfileService


def test_browser_profile_must_be_managed_and_non_overlapping(tmp_path: Path):
    service = IsolatedBrowserProfileService(tmp_path / "profiles")
    assert service.validate_isolated_profile_path(tmp_path / "profiles" / "p1", [tmp_path / "journal"]).name == "p1"
    with pytest.raises(BrowserProfileIsolationError):
        service.validate_isolated_profile_path(tmp_path / "journal" / "profile", [tmp_path / "journal"])
