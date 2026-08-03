"""Credential boundary; plaintext is never serialized by this module."""

from __future__ import annotations

from dataclasses import dataclass
from secrets import token_urlsafe


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
