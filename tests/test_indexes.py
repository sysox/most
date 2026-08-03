from pathlib import Path

from most.persistence import PersistenceCoordinator
from most.repositories import IndexService, RawYamlRepository


def test_indexes_are_rebuildable_caches(tmp_path: Path):
    store = PersistenceCoordinator(tmp_path)
    repository = RawYamlRepository(store, "records")
    repository.save("one", {"record_id": "one", "value": 1})
    index = IndexService(store).rebuild_yaml_index("records", "records")
    assert index.exists()
    index.unlink()
    rebuilt = IndexService(store).rebuild_yaml_index("records", "records")
    assert rebuilt.exists()
