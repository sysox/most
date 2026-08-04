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


def test_corrupt_workspace_lease_is_recoverable(tmp_path: Path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "workspaces").mkdir()
    (data_root / "workspaces/w.lease.yaml").write_text("heartbeat_at: incomplete\n", encoding="utf-8")
    lease = WorkspaceService(data_root, tmp_path).acquire_lease("w", "s1")
    assert lease.session_id == "s1"


def test_workspace_lease_timeout_overrides_live_process(tmp_path: Path):
    service = WorkspaceService(tmp_path / "data", tmp_path)
    lease = service.acquire_lease("w", "s1", timeout_seconds=1)
    from dataclasses import replace

    expired = replace(lease, heartbeat_at="2000-01-01T00:00:00Z")
    assert service._lease_is_active(expired) is False
