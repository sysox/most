from pathlib import Path

from most.artifacts import ArtifactStore


def test_artifact_write_has_no_fixed_temp_file(tmp_path: Path):
    source = tmp_path / "source.bin"
    source.write_bytes(b"content")
    store = ArtifactStore(tmp_path / "data")
    metadata = store.put(source)
    target = tmp_path / "data" / metadata["storage_path"]
    assert target.read_bytes() == b"content"
    assert not list(target.parent.glob("*.tmp"))
