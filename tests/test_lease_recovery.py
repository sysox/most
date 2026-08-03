from pathlib import Path

import yaml

from most.persistence import PersistenceCoordinator


def test_stale_lease_recovery_is_audited(tmp_path: Path):
    store = PersistenceCoordinator(tmp_path)
    (tmp_path / ".data-root.lease.yaml").write_text(yaml.safe_dump({
        "lease_id": "stale", "process_id": 999999999, "host_identifier": "local-host",
        "started_at": "now", "heartbeat_at": "now", "lease_timeout_seconds": 1,
    }), encoding="utf-8")
    # Force the host check to classify this test lease as foreign/stale through a
    # process id that cannot exist locally and the current host identifier.
    import socket
    values = yaml.safe_load((tmp_path / ".data-root.lease.yaml").read_text())
    values["host_identifier"] = socket.gethostname()
    (tmp_path / ".data-root.lease.yaml").write_text(yaml.safe_dump(values), encoding="utf-8")
    store.acquire_data_root_lease()
    events = store.read_jsonl("diagnostics/lease-events.jsonl")
    assert events[0]["event_type"] == "stale_lease_recovered"
