from pathlib import Path

from most.paths import application_data_root, managed_browser_profile_root
from most.persistence import PersistenceCoordinator


def test_managed_paths_are_nested_under_application_root():
    root = application_data_root("test-most")
    assert managed_browser_profile_root("test-most").parent == root


def test_atomic_write_uses_configured_retry_budget(tmp_path: Path):
    store = PersistenceCoordinator(tmp_path, replace_retries=1, retry_delay_seconds=0)
    assert store.write_json("value.json", {"ok": True}).exists()
