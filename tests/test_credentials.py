from pathlib import Path

from cryptography.fernet import Fernet

from most.credentials import EncryptedFileCredentialStore


def test_encrypted_file_store_never_writes_plaintext(tmp_path: Path):
    store = EncryptedFileCredentialStore(tmp_path, Fernet.generate_key())
    reference = store.create("api-key", "top-secret")
    stored = next(tmp_path.iterdir()).read_bytes()
    assert b"top-secret" not in stored
    assert store.resolve(reference) == "top-secret"
    store.delete(reference)
