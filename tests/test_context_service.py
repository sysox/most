from pathlib import Path

import pytest

from most.context import ContextOverflowError
from most.models import AIConfiguration, IntermediateResult, OverflowPolicy
from most.services import SessionService


def test_context_assembly_is_persisted_and_policy_is_explicit(tmp_path: Path):
    service = SessionService(tmp_path)
    session = service.create("context")
    result = service.add_result(IntermediateResult(session_id=session.id, interaction_id="i"), "answer")
    configuration = AIConfiguration(context_overflow_policy=OverflowPolicy.FAIL)
    with pytest.raises(ContextOverflowError):
        service.assemble_request_context(session, "i", result.id, [{"content": "x" * 100}], configuration, 1)
    configuration.context_overflow_policy = OverflowPolicy.TRIM_OLDEST
    selected, record = service.assemble_request_context(session, "i", result.id, [{"content": "x" * 100}], configuration, 1)
    assert selected == []
    assert "trimmed" in record.transformations[-1]
