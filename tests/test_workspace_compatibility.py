import subprocess
from pathlib import Path

from most.workspace import WorkspaceService


def test_workspace_compatibility_report_exposes_isolation_decision(tmp_path: Path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "test"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@example.invalid"], check=True)
    (tmp_path / "file.txt").write_text("content", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "file.txt"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "initial"], check=True)
    report = WorkspaceService(tmp_path / "data", tmp_path).compatibility_report()
    assert report["is_repository"] is True
    assert report["selected_fallback"] == "DEDICATED_WORKTREE"
