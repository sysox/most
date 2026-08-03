"""Content-addressed artifact storage."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path


class ArtifactStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def put(self, source: Path, *, media_type: str = "application/octet-stream", original_name: str | None = None) -> dict[str, object]:
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        relative = Path("artifacts") / "sha256" / digest[:2] / digest
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
            temporary = Path(temporary_name)
            try:
                with os.fdopen(fd, "wb") as handle, source.open("rb") as input_handle:
                    shutil.copyfileobj(input_handle, handle)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, target)
            except Exception:
                temporary.unlink(missing_ok=True)
                raise
        return {
            "sha256": digest,
            "media_type": media_type,
            "size": source.stat().st_size,
            "original_name": original_name or source.name,
            "storage_path": str(relative),
        }

    def verify(self, digest: str) -> bool:
        target = self.root / "artifacts" / "sha256" / digest[:2] / digest
        return target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == digest
