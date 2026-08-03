"""Safe Git command boundary using argument arrays."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class GitResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class GitService:
    def __init__(self, repository: Path):
        self.repository = Path(repository)

    def run(self, *arguments: str) -> GitResult:
        completed = subprocess.run(
            ["git", *arguments], cwd=self.repository, text=True,
            capture_output=True, check=False,
        )
        result = GitResult(("git", *arguments), completed.returncode, completed.stdout, completed.stderr)
        if result.returncode:
            raise RuntimeError(f"git command failed ({result.returncode}): {result.stderr.strip()}")
        return result

    def is_repository(self) -> bool:
        result = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=self.repository, text=True, capture_output=True, check=False)
        return result.returncode == 0 and result.stdout.strip() == "true"

    def status(self) -> str:
        return self.run("status", "--porcelain=v1").stdout

    def diff(self) -> str:
        return self.run("diff", "--no-ext-diff", "--binary").stdout

    def current_commit(self) -> str:
        return self.run("rev-parse", "HEAD").stdout.strip()

    def create_branch(self, branch: str, start_point: str = "HEAD") -> GitResult:
        self._validate_ref(branch)
        return self.run("switch", "--create", branch, start_point)

    def create_worktree(self, destination: Path, branch: str, start_point: str = "HEAD") -> GitResult:
        self._validate_ref(branch)
        destination = destination.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        return self.run("worktree", "add", "-b", branch, str(destination), start_point)

    def checkpoint(self, paths: list[str], *, message: str, trailers: dict[str, str]) -> str:
        if not paths:
            raise ValueError("checkpoint requires at least one path")
        self.run("add", "--", *paths)
        trailer_args = [f"{key}: {value}" for key, value in trailers.items()]
        full_message = message + ("\n\n" + "\n".join(trailer_args) if trailer_args else "")
        self.run("commit", "-m", full_message)
        return self.current_commit()

    @staticmethod
    def _validate_ref(value: str) -> None:
        if not value or value.startswith("-") or ".." in value or "@{" in value:
            raise ValueError("unsafe Git ref")
