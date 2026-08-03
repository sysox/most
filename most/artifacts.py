"""Content-addressed artifact storage."""

from __future__ import annotations

import hashlib
import shutil
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
            temporary = target.with_name(f".{target.name}.tmp")
            shutil.copyfile(source, temporary)
            temporary.replace(target)
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
