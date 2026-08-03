"""Credential boundary; plaintext is never serialized by this module."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from secrets import token_urlsafe

from cryptography.fernet import Fernet, InvalidToken


@dataclass(frozen=True, slots=True)
class CredentialReference:
    id: str
    credential_type: str
    storage_backend: str
    storage_key: str
    display_name: str


@dataclass(frozen=True, slots=True)
class CredentialHandle:
    handle_id: str
    reference_id: str
    expires_at: str

    def __str__(self) -> str:
        return self.handle_id


class CredentialService:
    """Issues short-lived opaque handles over a backend credential store."""

    def __init__(self, backend):
        self.backend = backend
        self._references: dict[str, CredentialReference] = {}
        self._handles: dict[str, tuple[CredentialHandle, CredentialReference]] = {}

    def register(self, reference: CredentialReference) -> None:
        self._references[reference.id] = reference

    def issue_handle(self, reference: CredentialReference, ttl_seconds: int = 60) -> CredentialHandle:
        if ttl_seconds <= 0:
            raise ValueError("credential handle TTL must be positive")
        self.register(reference)
        expires = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        handle = CredentialHandle(token_urlsafe(24), reference.id, expires.isoformat(timespec="milliseconds").replace("+00:00", "Z"))
        self._handles[handle.handle_id] = (handle, reference)
        return handle

    def resolve_handle(self, handle: CredentialHandle) -> str:
        stored = self._handles.get(handle.handle_id)
        if stored is None or stored[0] != handle:
            raise PermissionError("unknown credential handle")
        if datetime.now(UTC) >= datetime.fromisoformat(handle.expires_at):
            self._handles.pop(handle.handle_id, None)
            raise PermissionError("credential handle expired")
        return self.backend.resolve(stored[1])

    def revoke_handle(self, handle: CredentialHandle) -> None:
        self._handles.pop(handle.handle_id, None)


class InMemoryCredentialStore:
    """Test/development store. Production should provide an OS secret-store backend."""

    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def create(self, credential_type: str, value: str, display_name: str = "") -> CredentialReference:
        key = token_urlsafe(18)
        self._values[key] = value
        return CredentialReference(token_urlsafe(12), credential_type, "memory", key, display_name)

    def resolve(self, reference: CredentialReference) -> str:
        if reference.storage_backend != "memory":
            raise ValueError("unsupported credential backend")
        try:
            return self._values[reference.storage_key]
        except KeyError as exc:
            raise KeyError("credential not found") from exc

    def delete(self, reference: CredentialReference) -> None:
        self._values.pop(reference.storage_key, None)


class EncryptedFileCredentialStore:
    """Encrypted credential backend.

    `master_key` must come from a native OS secret store or an explicitly supplied
    process secret. This class never creates or persists the master key.
    """

    def __init__(self, root: Path, master_key: bytes):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._cipher = Fernet(master_key)

    def create(self, credential_type: str, value: str, display_name: str = "") -> CredentialReference:
        key = token_urlsafe(18)
        (self.root / key).write_bytes(self._cipher.encrypt(value.encode("utf-8")))
        return CredentialReference(token_urlsafe(12), credential_type, "encrypted-file", key, display_name)

    def resolve(self, reference: CredentialReference) -> str:
        if reference.storage_backend != "encrypted-file":
            raise ValueError("unsupported credential backend")
        try:
            encrypted = (self.root / reference.storage_key).read_bytes()
            return self._cipher.decrypt(encrypted).decode("utf-8")
        except (OSError, InvalidToken, UnicodeDecodeError) as exc:
            raise KeyError("credential unavailable") from exc

    def delete(self, reference: CredentialReference) -> None:
        (self.root / reference.storage_key).unlink(missing_ok=True)
