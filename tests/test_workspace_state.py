import subprocess
from pathlib import Path

import pytest

from most.workspace import WorkspaceService


def test_workspace_divergence_is_detected(tmp_path: Path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, stdin=subprocess.DEVNULL)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "test"], check=True, stdin=subprocess.DEVNULL)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@example.invalid"], check=True, stdin=subprocess.DEVNULL)
    file = tmp_path / "file.txt"
    file.write_text("one", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "file.txt"], check=True, stdin=subprocess.DEVNULL)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "commit.gpgSign=false", "commit", "-qm", "initial"], check=True, stdin=subprocess.DEVNULL)
    service = WorkspaceService(tmp_path / "data", tmp_path)
    state = service.capture_workspace_state()
    file.write_text("two", encoding="utf-8")
    with pytest.raises(RuntimeError, match="WORKSPACE_DIVERGED"):
        service.assert_workspace_unchanged(state)
