from pathlib import Path

import pytest

from most.workspace import WorkspaceService


def test_workspace_lease_is_single_writer(tmp_path: Path):
    service = WorkspaceService(tmp_path / "data", tmp_path)
    first = service.acquire_lease("w", "s1")
    with pytest.raises(RuntimeError):
        service.acquire_lease("w", "s2")
    service.release_lease("w", first.lease_id)
    service.acquire_lease("w", "s2")
