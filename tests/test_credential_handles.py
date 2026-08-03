from dataclasses import replace
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from most.credentials import CredentialService, EncryptedFileCredentialStore


def test_credential_handles_are_opaque_short_lived_and_revocable(tmp_path: Path):
    backend = EncryptedFileCredentialStore(tmp_path, Fernet.generate_key())
    reference = backend.create("api-key", "secret")
    service = CredentialService(backend)
    handle = service.issue_handle(reference, ttl_seconds=60)
    assert "secret" not in str(handle)
    assert service.resolve_handle(handle) == "secret"
    service.revoke_handle(handle)
    with pytest.raises(PermissionError):
        service.resolve_handle(handle)


def test_expired_credential_handle_is_rejected(tmp_path: Path):
    backend = EncryptedFileCredentialStore(tmp_path, Fernet.generate_key())
    reference = backend.create("api-key", "secret")
    service = CredentialService(backend)
    handle = service.issue_handle(reference, ttl_seconds=1)
    expired = replace(handle, expires_at="2000-01-01T00:00:00.000Z")
    service._handles[expired.handle_id] = (expired, reference)
    with pytest.raises(PermissionError, match="expired"):
        service.resolve_handle(expired)
