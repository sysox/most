from pathlib import Path

import pytest

from most.workspace import WorkspaceService


def test_workspace_finalization_requires_confirmation(tmp_path: Path):
    service = WorkspaceService(tmp_path / "data", tmp_path)
    with pytest.raises(PermissionError):
        service.finalize_workspace_session("s", "DISCARD_BRANCH")
    assert service.finalize_workspace_session("s", "KEEP_DETAILED_HISTORY") == "KEEP_DETAILED_HISTORY"
