from pathlib import Path

from cryptography.fernet import Fernet

from most.credentials import EncryptedFileCredentialStore, KeyringCredentialStore


def test_encrypted_file_store_never_writes_plaintext(tmp_path: Path):
    store = EncryptedFileCredentialStore(tmp_path, Fernet.generate_key())
    reference = store.create("api-key", "top-secret")
    stored = next(tmp_path.iterdir()).read_bytes()
    assert b"top-secret" not in stored
    assert store.resolve(reference) == "top-secret"
    store.delete(reference)


def test_keyring_store_round_trips_without_persisting_in_most(tmp_path: Path, monkeypatch):
    values = {}
    import keyring

    monkeypatch.setattr(keyring, "set_password", lambda service, name, value: values.__setitem__((service, name), value))
    monkeypatch.setattr(keyring, "get_password", lambda service, name: values.get((service, name)))
    monkeypatch.setattr(keyring, "delete_password", lambda service, name: values.pop((service, name), None))
    store = KeyringCredentialStore()
    reference = store.create("openai", "top-secret")
    assert reference.storage_backend == "keyring"
    assert store.resolve(reference) == "top-secret"
    store.delete(reference)
    assert values == {}
