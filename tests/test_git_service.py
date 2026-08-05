import subprocess
from pathlib import Path

import pytest

from most.git_service import GitService


def test_git_ref_validation(tmp_path: Path):
    service = GitService(tmp_path)
    with pytest.raises(ValueError):
        service.create_branch("--dangerous")


def test_git_service_can_initialize_selected_directory(tmp_path: Path):
    repository = tmp_path / "new-repository"
    repository.mkdir()
    service = GitService(repository)
    service.initialize_repository()
    assert service.is_repository()


def test_git_checkpoint_and_isolated_worktree(tmp_path: Path):
    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(["git", "init", "-q", str(repository)], check=True, stdin=subprocess.DEVNULL)
    subprocess.run(["git", "-C", str(repository), "config", "user.name", "test"], check=True, stdin=subprocess.DEVNULL)
    subprocess.run(["git", "-C", str(repository), "config", "user.email", "test@example.invalid"], check=True, stdin=subprocess.DEVNULL)
    (repository / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repository), "add", "README.md"], check=True, stdin=subprocess.DEVNULL)
    subprocess.run(["git", "-C", str(repository), "-c", "commit.gpgSign=false", "commit", "-qm", "initial"], check=True, stdin=subprocess.DEVNULL)
    service = GitService(repository)
    worktree = tmp_path / "worktree"
    service.create_worktree(worktree, "ai/test", service.current_commit())
    (worktree / "change.txt").write_text("change\n", encoding="utf-8")
    commit = GitService(worktree).checkpoint(["change.txt"], message="AI iteration", trailers={"Session": "s1", "Iteration": "1"})
    assert len(commit) == 40


def test_git_diff_defaults_to_index_and_accepts_ref(tmp_path: Path):
    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(["git", "init", "-q", str(repository)], check=True, stdin=subprocess.DEVNULL)
    subprocess.run(["git", "-C", str(repository), "config", "user.name", "test"], check=True, stdin=subprocess.DEVNULL)
    subprocess.run(["git", "-C", str(repository), "config", "user.email", "test@example.invalid"], check=True, stdin=subprocess.DEVNULL)
    tracked = repository / "README.md"
    tracked.write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repository), "add", "README.md"], check=True, stdin=subprocess.DEVNULL)
    subprocess.run(["git", "-C", str(repository), "-c", "commit.gpgSign=false", "commit", "-qm", "initial"], check=True, stdin=subprocess.DEVNULL)
    tracked.write_text("unstaged\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repository), "add", "README.md"], check=True, stdin=subprocess.DEVNULL)
    tracked.write_text("worktree\n", encoding="utf-8")

    service = GitService(repository)
    assert "base" not in service.diff()
    assert "base" in service.diff("HEAD")
