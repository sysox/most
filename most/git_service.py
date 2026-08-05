"""Safe Git command boundary using argument arrays."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

INSPECTION_TIMEOUT_SECONDS = 5


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
            capture_output=True, check=False, stdin=subprocess.DEVNULL,
        )
        result = GitResult(("git", *arguments), completed.returncode, completed.stdout, completed.stderr)
        if result.returncode:
            raise RuntimeError(f"git command failed ({result.returncode}): {result.stderr.strip()}")
        return result

    def is_repository(self) -> bool:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"], cwd=self.repository,
            text=True, capture_output=True, check=False, stdin=subprocess.DEVNULL,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"

    def initialize_repository(self) -> GitResult:
        """Initialize a repository only at this explicitly selected path."""
        if self.is_repository():
            return GitResult(("git", "init"), 0, "already a repository", "")
        return self.run("init")

    def status(self) -> str:
        return self.run("status", "--porcelain=v1").stdout

    def changed_paths(self) -> list[str]:
        """Return changed destination paths, including Git rename targets."""
        fields = self.run("status", "--porcelain=v1", "-z").stdout.split("\0")
        paths: list[str] = []
        index = 0
        while index < len(fields):
            entry = fields[index]
            index += 1
            if len(entry) < 4:
                continue
            status, path = entry[:2], entry[3:]
            if status and status[0] in {"R", "C"} and index < len(fields):
                path = fields[index]
                index += 1
            if path:
                paths.append(path)
        return paths

    def diff(self, against: str | None = None) -> str:
        arguments = ["diff", "--no-ext-diff", "--binary"]
        if against:
            arguments.append(against)
        return self.run(*arguments).stdout

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

    def create_isolated_clone(self, destination: Path, branch: str, start_point: str = "HEAD") -> GitResult:
        self._validate_ref(branch)
        destination = destination.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(
            ["git", "clone", "--no-hardlinks", str(self.repository), str(destination)],
            text=True, capture_output=True, check=False, stdin=subprocess.DEVNULL,
        )
        if completed.returncode:
            raise RuntimeError(f"git clone failed ({completed.returncode}): {completed.stderr.strip()}")
        clone = GitService(destination)
        clone.run("switch", "--create", branch, start_point)
        return GitResult(("git", "clone", "--no-hardlinks"), completed.returncode, completed.stdout, completed.stderr)

    def inspect_submodules(self) -> dict[str, object]:
        try:
            result = subprocess.run(
                ["git", "submodule", "status", "--recursive"], cwd=self.repository,
                text=True, capture_output=True, check=False, stdin=subprocess.DEVNULL,
                timeout=INSPECTION_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return {"available": False, "status": "", "error": "git submodule inspection timed out"}
        return {"available": result.returncode == 0, "status": result.stdout, "error": result.stderr if result.returncode else None}

    def inspect_lfs(self) -> dict[str, object]:
        if shutil.which("git-lfs") is None:
            return {"available": False, "required": False, "reason": "git-lfs executable unavailable"}
        try:
            result = subprocess.run(
                ["git", "lfs", "ls-files"], cwd=self.repository,
                text=True, capture_output=True, check=False, stdin=subprocess.DEVNULL,
                timeout=INSPECTION_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return {"available": False, "required": False, "files": [], "reason": "git-lfs inspection timed out"}
        return {"available": result.returncode == 0, "required": bool(result.stdout.strip()), "files": result.stdout.splitlines()}

    def check_path_length_support(self, candidate: Path, max_length: int = 240) -> dict[str, object]:
        longest = max((len(str(path)) for path in candidate.rglob("*") if path.exists()), default=len(str(candidate)))
        supported = os.name != "nt" or longest <= max_length
        return {"supported": supported, "longest_path": longest, "limit": max_length}

    def list_commits(self, limit: int = 50) -> list[str]:
        if limit < 1:
            raise ValueError("limit must be positive")
        return self.run("log", f"-{limit}", "--format=%H").stdout.splitlines()

    def restore_commit(self, commit: str, *, confirm: bool = False) -> GitResult:
        self._validate_ref(commit)
        if not confirm:
            raise PermissionError("restoring a Git commit requires explicit confirmation")
        return self.run("reset", "--hard", commit)

    def checkpoint(self, paths: list[str], *, message: str, trailers: dict[str, str]) -> str:
        if not paths:
            raise ValueError("checkpoint requires at least one path")
        self.run("add", "--", *paths)
        trailer_args = [f"{key}: {value}" for key, value in trailers.items()]
        full_message = message + ("\n\n" + "\n".join(trailer_args) if trailer_args else "")
        self.run("commit", "-m", full_message)
        return self.current_commit()

    def stash_push(self, message: str) -> str:
        result = self.run("stash", "push", "--include-untracked", "-m", message)
        if "No local changes" in result.stdout:
            raise RuntimeError("no user changes available for snapshot")
        listing = self.run("stash", "list", "-1", "--format=%gd").stdout.strip()
        if not listing:
            raise RuntimeError("stash was not created")
        return listing

    def apply_patch_file(self, patch_path: Path) -> GitResult:
        patch_path = patch_path.resolve()
        if not patch_path.is_file():
            raise FileNotFoundError(patch_path)
        return self.run("apply", "--whitespace=nowarn", str(patch_path))

    @staticmethod
    def _validate_ref(value: str) -> None:
        if not value or value.startswith("-") or ".." in value or "@{" in value:
            raise ValueError("unsafe Git ref")
