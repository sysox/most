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


def test_workspace_context_is_included_and_recorded(tmp_path: Path):
    (tmp_path / "main.py").write_text("print('safe')\n", encoding="utf-8")
    service = SessionService(tmp_path / "data")
    session = service.create("workspace")
    result = service.add_result(IntermediateResult(session_id=session.id, interaction_id="i"), "answer")
    configuration = AIConfiguration(workspace_context_strategy="EXPLICIT_SELECTION")
    selected, record = service.assemble_request_context(
        session,
        "i",
        result.id,
        [{"role": "user", "content": "review this"}],
        configuration,
        100,
        workspace_repository=tmp_path,
        workspace_paths=("main.py",),
    )
    assert selected[0]["content"].startswith("[workspace file: main.py]")
    assert record.workspace_context_strategy == "EXPLICIT_SELECTION"
    assert record.metadata["workspace_files"][0]["path"] == "main.py"
