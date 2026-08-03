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
