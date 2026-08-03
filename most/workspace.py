"""Workspace safety primitives: leases, dirty-state policy, and isolation tiers."""

from __future__ import annotations

import os
import socket
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path

from .git_service import GitService
from .models import new_id, utc_now
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
