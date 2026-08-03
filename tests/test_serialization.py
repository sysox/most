import json
from pathlib import Path

import pytest

from most.models import AIConfiguration, ExecutionState, record_payload
from most.persistence import PersistenceCoordinator
from most.serialization import validate_header, versioned_payload


def test_nested_enum_values_are_canonical():
    payload = record_payload(AIConfiguration(adapter_options={"state": ExecutionState.READY}), record_type="AI_CONFIGURATION")
    assert payload["adapter_options"]["state"] == "ready"
    assert validate_header(payload).record_type == "AI_CONFIGURATION"


def test_jsonl_events_have_flattened_headers(tmp_path: Path):
    store = PersistenceCoordinator(tmp_path)
    store.append_versioned_jsonl("events.jsonl", [{"event_type": "STATUS"}], record_type="STATUS_EVENT")
    line = json.loads((tmp_path / "events.jsonl").read_text(encoding="utf-8"))
    assert validate_header(line).record_type == "STATUS_EVENT"


def test_header_validation_rejects_missing_fields():
    with pytest.raises(ValueError):
        validate_header({"record_type": "X"})
