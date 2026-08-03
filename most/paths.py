"""Platform-managed application paths."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def application_data_root(application_name: str = "most") -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / application_name
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / application_name
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / application_name


def managed_browser_profile_root(application_name: str = "most") -> Path:
    return application_data_root(application_name) / "browser-profiles"


def managed_temporary_workspace_root(application_name: str = "most") -> Path:
    return application_data_root(application_name) / "temporary-workspaces"
