from pathlib import Path

import pytest

from most.artifacts import ArtifactStore
from most.execution import transition
from most.models import Execution, ExecutionState


def test_execution_terminal_state_cannot_transition():
    execution = Execution(state=ExecutionState.CREATED)
    execution, _ = transition(execution, ExecutionState.VALIDATING)
    execution, _ = transition(execution, ExecutionState.FAILED)
    with pytest.raises(ValueError):
        transition(execution, ExecutionState.READY)


def test_artifact_store_is_content_addressed(tmp_path: Path):
    source = tmp_path / "input.txt"
    source.write_text("hello", encoding="utf-8")
    store = ArtifactStore(tmp_path / "data")
    first = store.put(source, media_type="text/plain")
    second = store.put(source, media_type="text/plain")
    assert first["sha256"] == second["sha256"]
    assert store.verify(str(first["sha256"]))
