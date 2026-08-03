"""Credential boundary; plaintext is never serialized by this module."""

from __future__ import annotations

from dataclasses import dataclass
from secrets import token_urlsafe
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


@dataclass(frozen=True, slots=True)
class CredentialReference:
    id: str
    credential_type: str
    storage_backend: str
    storage_key: str
    display_name: str


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
