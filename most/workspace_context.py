"""Conservative workspace source-context selection and manifests."""

from __future__ import annotations

import fnmatch
import hashlib
from dataclasses import dataclass
from pathlib import Path

from .git_service import GitService

SECRET_NAMES = {".env", ".env.local", "id_rsa", "credentials.json", "secrets.yaml", "secrets.yml"}
GENERATED_PARTS = {".git", "node_modules", "__pycache__", "dist", "build"}


@dataclass(frozen=True, slots=True)
class WorkspaceFile:
    path: str
    sha256: str
    size: int
    content: str


@dataclass(frozen=True, slots=True)
class WorkspaceContextSelection:
    strategy: str
    files: tuple[WorkspaceFile, ...]
    excluded_paths: tuple[str, ...]
    git_diff: str | None = None


class WorkspaceContextSelector:
    def __init__(self, repository: Path):
        self.repository = Path(repository).resolve()
        self.git = GitService(self.repository)

    def select(
        self,
        strategy: str,
        explicit_paths: tuple[str, ...] = (),
        include_patterns: tuple[str, ...] = (),
        exclude_patterns: tuple[str, ...] = (),
        include_git_diff: bool = False,
        max_files: int | None = None,
        max_bytes: int | None = None,
    ) -> WorkspaceContextSelection:
        if strategy == "EXPLICIT_SELECTION":
            candidates = [self.repository / path for path in explicit_paths]
        elif strategy in {"CHANGED_FILES", "GIT_DIFF_ONLY", "HYBRID"}:
            changed = [line[3:] for line in self.git.status().splitlines() if len(line) >= 4]
            candidates = [self.repository / path for path in changed]
        elif strategy in {"REPOSITORY_MAP", "SYMBOL_SUMMARY", "SNIPPET_WINDOWS"}:
            candidates = list(self.repository.rglob("*"))
        elif strategy == "ADAPTER_NATIVE":
            raise PermissionError("ADAPTER_NATIVE requires an approved adapter filesystem scope")
        else:
            raise ValueError(f"unsupported workspace context strategy: {strategy}")

        if strategy == "GIT_DIFF_ONLY":
            include_git_diff = True
        files: list[WorkspaceFile] = []
        excluded: list[str] = []
        total_bytes = 0
        for candidate in candidates:
            try:
                path = candidate.resolve()
                relative = path.relative_to(self.repository).as_posix()
            except ValueError:
                excluded.append(str(candidate))
                continue
            if not path.is_file() or self._excluded(relative, include_patterns, exclude_patterns):
                excluded.append(relative)
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
            data = content.encode("utf-8")
            if max_files is not None and len(files) >= max_files:
                excluded.append(relative)
                continue
            if max_bytes is not None and total_bytes + len(data) > max_bytes:
                excluded.append(relative)
                continue
            files.append(WorkspaceFile(relative, hashlib.sha256(data).hexdigest(), len(data), content))
            total_bytes += len(data)
        diff = self.git.diff() if include_git_diff and self.git.is_repository() else None
        return WorkspaceContextSelection(strategy, tuple(files), tuple(sorted(set(excluded))), diff)

    @staticmethod
    def _excluded(relative: str, include_patterns: tuple[str, ...], exclude_patterns: tuple[str, ...]) -> bool:
        parts = set(Path(relative).parts)
        name = Path(relative).name
        if parts & GENERATED_PARTS or name in SECRET_NAMES or (name.startswith(".") and name != ".gitignore"):
            return True
        if include_patterns and not any(fnmatch.fnmatch(relative, pattern) for pattern in include_patterns):
            return True
        return any(fnmatch.fnmatch(relative, pattern) for pattern in exclude_patterns)
