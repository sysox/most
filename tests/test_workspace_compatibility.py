from pathlib import Path

from most.git_service import GitService
from most.workspace import WorkspaceService


def test_workspace_compatibility_report_exposes_isolation_decision(tmp_path: Path):
    git = GitService(tmp_path)
    git.initialize_repository()
    git.run("config", "user.name", "test")
    git.run("config", "user.email", "test@example.invalid")
    (tmp_path / "file.txt").write_text("content", encoding="utf-8")
    git.run("add", "file.txt")
    git.run("-c", "commit.gpgSign=false", "commit", "-qm", "initial")
    report = WorkspaceService(tmp_path / "data", tmp_path).compatibility_report()
    assert report["is_repository"] is True
    assert report["selected_fallback"] == "DEDICATED_WORKTREE"
