"""Workspace safety primitives: leases, dirty-state policy, and isolation tiers."""

from __future__ import annotations

import hashlib
import os
import socket
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

import yaml

from .git_service import GitService
from .models import AIIteration, new_id, record_payload, utc_now
from .persistence import PersistenceCoordinator


@dataclass(frozen=True, slots=True)
class WorkspaceLease:
    lease_id: str
    session_id: str
    process_id: int
    host_identifier: str
    started_at: str
    heartbeat_at: str
    lease_timeout_seconds: int


class DirtyTreePolicy(str, Enum):
    REQUIRE_CLEAN = "REQUIRE_CLEAN"
    ISOLATE_FROM_HEAD = "ISOLATE_FROM_HEAD"
    IMPORT_USER_SNAPSHOT = "IMPORT_USER_SNAPSHOT"
    STASH_WITH_CONFIRMATION = "STASH_WITH_CONFIRMATION"


@dataclass(frozen=True, slots=True)
class WorkspaceIsolation:
    tier: str
    repository: Path
    base_commit: str
    branch: str | None
    dirty_status: str
    user_snapshot_reference: str | None = None


@dataclass(frozen=True, slots=True)
class WorkspaceState:
    git_status: str
    file_hashes: dict[str, str]


class WorkspaceService:
    def __init__(self, data_root: Path, repository: Path):
        self.store = PersistenceCoordinator(data_root)
        self.repository = Path(repository)
        self.git = GitService(self.repository)

    def acquire_lease(self, workspace_id: str, session_id: str, timeout_seconds: int = 300) -> WorkspaceLease:
        relative = f"workspaces/{workspace_id}.lease.yaml"
        existing = self._read_lease(relative)
        if existing and self._lease_is_active(existing):
            raise RuntimeError("workspace already has an active lease")
        now = utc_now()
        lease = WorkspaceLease(new_id(), session_id, os.getpid(), socket.gethostname(), now, now, timeout_seconds)
        self.store.write_yaml(relative, asdict(lease))
        return lease

    def heartbeat(self, workspace_id: str, lease: WorkspaceLease) -> WorkspaceLease:
        updated = WorkspaceLease(lease.lease_id, lease.session_id, lease.process_id, lease.host_identifier,
                                 lease.started_at, utc_now(), lease.lease_timeout_seconds)
        self.store.write_yaml(f"workspaces/{workspace_id}.lease.yaml", asdict(updated))
        return updated

    def release_lease(self, workspace_id: str, lease_id: str) -> None:
        relative = f"workspaces/{workspace_id}.lease.yaml"
        current = self._read_lease(relative)
        if current and current.lease_id != lease_id:
            raise RuntimeError("lease ownership mismatch")
        path = self.store.root / relative
        if path.exists():
            path.unlink()

    def inspect(self) -> dict[str, object]:
        return {
            "is_repository": self.git.is_repository(),
            "status": self.git.status() if self.git.is_repository() else "",
            "current_commit": self.git.current_commit() if self.git.is_repository() else None,
        }

    def prepare_ai_workspace(self, session_id: str, destination: Path | None = None,
                             policy: DirtyTreePolicy = DirtyTreePolicy.ISOLATE_FROM_HEAD,
                             *, confirmation: bool = False, snapshot_patch: Path | None = None) -> WorkspaceIsolation:
        if not self.git.is_repository():
            raise ValueError("workspace must be an existing Git repository")
        status = self.git.status()
        base = self.git.current_commit()
        if status and policy is DirtyTreePolicy.REQUIRE_CLEAN:
            raise RuntimeError("working tree is not clean")
        snapshot_reference = None
        if status and policy is DirtyTreePolicy.STASH_WITH_CONFIRMATION:
            if not confirmation:
                raise PermissionError("dirty-tree stashing requires explicit confirmation")
            snapshot_reference = self.git.stash_push(f"most user baseline {session_id}")
            status = self.git.status()
        if policy is DirtyTreePolicy.IMPORT_USER_SNAPSHOT and (not confirmation or snapshot_patch is None):
            raise PermissionError("user snapshot import requires explicit confirmation and a patch")
        if destination is None:
            destination = self.store.root / "temporary-workspaces" / session_id
        branch = f"ai/{session_id}"
        if policy is DirtyTreePolicy.ISOLATE_FROM_HEAD:
            try:
                self.git.create_worktree(destination, branch, base)
                return WorkspaceIsolation("DEDICATED_WORKTREE", destination, base, branch, status, snapshot_reference)
            except RuntimeError:
                if destination.exists():
                    raise
                self.git.create_isolated_clone(destination, branch, base)
                return WorkspaceIsolation("ISOLATED_TEMPORARY_CLONE", destination, base, branch, status, snapshot_reference)
        if policy is DirtyTreePolicy.STASH_WITH_CONFIRMATION:
            self.git.create_worktree(destination, branch, base)
            return WorkspaceIsolation("DEDICATED_WORKTREE", destination, base, branch, status, snapshot_reference)
        if policy is DirtyTreePolicy.IMPORT_USER_SNAPSHOT:
            self.git.create_worktree(destination, branch, base)
            GitService(destination).apply_patch_file(snapshot_patch)  # type: ignore[arg-type]
            return WorkspaceIsolation("DEDICATED_WORKTREE_WITH_IMPORTED_SNAPSHOT", destination, base, branch, status, str(snapshot_patch))
        return WorkspaceIsolation("CURRENT_REPOSITORY", self.repository, base, None, status)

    def capture_workspace_state(self) -> WorkspaceState:
        if not self.git.is_repository():
            raise ValueError("workspace must be a Git repository")
        hashes: dict[str, str] = {}
        data_root = self.store.root.resolve()
        for path in self.repository.rglob("*"):
            if not path.is_file() or ".git" in path.parts:
                continue
            if data_root == path.resolve() or data_root in path.resolve().parents:
                continue
            relative = path.relative_to(self.repository).as_posix()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            hashes[relative] = digest
        return WorkspaceState(self.git.status(), hashes)

    def assert_workspace_unchanged(self, expected: WorkspaceState) -> None:
        current = self.capture_workspace_state()
        if current != expected:
            raise RuntimeError("WORKSPACE_DIVERGED")

    def create_iteration_checkpoint(self, iteration: AIIteration, paths: list[str], message: str) -> AIIteration:
        """Create one checkpoint using the two-phase linkage protocol."""
        if not self.git.is_repository():
            raise ValueError("workspace must be a Git repository")
        if iteration.base_commit is None:
            iteration.base_commit = self.git.current_commit()
        iteration.status = "ready_to_commit"
        self.store.write_yaml(
            f"workspaces/{iteration.session_id}/iterations/{iteration.sequence_number:04d}/iteration.yaml",
            record_payload(iteration, record_type="AI_ITERATION"),
        )
        commit = self.git.checkpoint(
            paths,
            message=message,
            trailers={
                "Session": iteration.session_id,
                "Iteration": str(iteration.sequence_number),
                "Execution": iteration.execution_id,
                "AI-Iteration": iteration.id,
            },
        )
        iteration.resulting_commit = commit
        iteration.status = "completed"
        iteration.completed_at = utc_now()
        self.store.write_yaml(
            f"workspaces/{iteration.session_id}/iterations/{iteration.sequence_number:04d}/iteration.yaml",
            record_payload(iteration, record_type="AI_ITERATION"),
        )
        return iteration

    def list_iterations(self, session_id: str) -> list[dict[str, object]]:
        directory = self.store.root / "workspaces" / session_id / "iterations"
        records = []
        for path in sorted(directory.glob("*/iteration.yaml")):
            value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(value, dict):
                records.append(value)
        return records

    def restore_iteration(self, session_id: str, sequence_number: int, *, confirm: bool = False) -> None:
        iterations = self.list_iterations(session_id)
        selected = next((item for item in iterations if item.get("sequence_number") == sequence_number), None)
        if selected is None or not selected.get("resulting_commit"):
            raise KeyError("iteration checkpoint not found")
        self.git.restore_commit(str(selected["resulting_commit"]), confirm=confirm)

    def finalize_workspace_session(self, session_id: str, action: str, *, confirm: bool = False) -> str:
        allowed = {"KEEP_DETAILED_HISTORY", "SQUASH_TO_ONE_COMMIT", "SQUASH_BY_APPROVED_ITERATION", "EXPORT_PATCH_SERIES", "DISCARD_BRANCH"}
        if action not in allowed:
            raise ValueError(f"unsupported finalization action: {action}")
        if action in {"SQUASH_TO_ONE_COMMIT", "SQUASH_BY_APPROVED_ITERATION", "DISCARD_BRANCH"} and not confirm:
            raise PermissionError("destructive workspace finalization requires explicit confirmation")
        return action

    def _read_lease(self, relative: str) -> WorkspaceLease | None:
        import yaml
        path = self.store.root / relative
        if not path.exists():
            return None
        values = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return WorkspaceLease(**values)

    def _lease_is_active(self, lease: WorkspaceLease) -> bool:
        if lease.host_identifier != socket.gethostname():
            return True
        try:
            os.kill(lease.process_id, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True
