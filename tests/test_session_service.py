from pathlib import Path

import pytest

from most.models import IntermediateResult, SessionMode
from most.services import SessionService


def test_communication_can_fork_to_immutable_workspace_session(tmp_path: Path):
    service = SessionService(tmp_path)
    communication = service.create("research")
    result = service.add_result(IntermediateResult(session_id=communication.id, interaction_id="i"), "answer")
    workspace = service.create_workspace_from_result(communication, result.id)
    assert communication.mode is SessionMode.COMMUNICATION
    assert workspace.mode is SessionMode.WORKSPACE
    assert workspace.origin_result_id == result.id


def test_result_selection_rejects_other_session(tmp_path: Path):
    service = SessionService(tmp_path)
    first = service.create("one")
    second = service.create("two")
    result = service.add_result(IntermediateResult(session_id=first.id, interaction_id="i"), "answer")
    with pytest.raises(KeyError):
        service.select_final_result(second, result.id)
