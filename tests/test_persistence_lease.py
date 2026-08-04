from pathlib import Path

import pytest

from most.persistence import PersistenceCoordinator


def test_data_root_lease_is_single_writer(tmp_path: Path):
    store = PersistenceCoordinator(tmp_path)
    lease = store.acquire_data_root_lease()
    with pytest.raises(RuntimeError):
        store.acquire_data_root_lease()
    store.release_data_root_lease(lease.lease_id)
    store.acquire_data_root_lease()


def test_corrupt_data_root_lease_is_recoverable(tmp_path: Path):
    (tmp_path / ".data-root.lease.yaml").write_text("heartbeat_at: incomplete\n", encoding="utf-8")
    lease = PersistenceCoordinator(tmp_path).acquire_data_root_lease()
    assert lease.lease_id


def test_data_root_lease_timeout_overrides_live_process():
    from most.persistence import PersistenceCoordinator

    assert PersistenceCoordinator._existing_lease_active({
        "heartbeat_at": "2000-01-01T00:00:00Z", "lease_timeout_seconds": 300,
        "host_identifier": "same-host", "process_id": 1,
    }) is False
