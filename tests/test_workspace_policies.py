import subprocess
from pathlib import Path

import pytest

from most.workspace import DirtyTreePolicy, WorkspaceService


def _repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "test"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.invalid"], check=True)
    (path / "file.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "file.txt"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "initial"], check=True)


def test_stash_policy_requires_confirmation_and_records_stash(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _repo(repo)
    (repo / "file.txt").write_text("user\n", encoding="utf-8")
    service = WorkspaceService(tmp_path / "data", repo)
    with pytest.raises(PermissionError):
        service.prepare_ai_workspace("s", policy=DirtyTreePolicy.STASH_WITH_CONFIRMATION)
    result = service.prepare_ai_workspace("s", policy=DirtyTreePolicy.STASH_WITH_CONFIRMATION, confirmation=True)
    assert result.user_snapshot_reference


def test_import_snapshot_requires_explicit_confirmation(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _repo(repo)
    patch = tmp_path / "changes.patch"
    patch.write_text("", encoding="utf-8")
    service = WorkspaceService(tmp_path / "data", repo)
    with pytest.raises(PermissionError):
        service.prepare_ai_workspace("s", policy=DirtyTreePolicy.IMPORT_USER_SNAPSHOT, snapshot_patch=patch)


def test_require_clean_uses_dedicated_worktree_when_clean(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _repo(repo)
    service = WorkspaceService(tmp_path / "data", repo)
    result = service.prepare_ai_workspace("s", policy=DirtyTreePolicy.REQUIRE_CLEAN)
    assert result.tier == "DEDICATED_WORKTREE"
    assert result.branch == "ai/s"
