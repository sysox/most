import json
from pathlib import Path

import pytest

from most.cli import main
from most.journal import JournalService
from most.models import IntermediateResult


def test_history_command_returns_pipeline_stages(tmp_path: Path, capsys):
    journal = JournalService(tmp_path)
    journal.record_result(
        IntermediateResult(
            id="result-1", session_id="session-1", interaction_id="interaction-1",
            profile="review", pipeline_id="pipe-1", stage_index=2,
            operation_id="pipe-1:stage-2",
        ),
        "prior result",
    )
    assert main(["--data-root", str(tmp_path), "history", "--pipeline-id", "pipe-1", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == [{
        "stage_index": 2,
        "operation_id": "pipe-1:stage-2",
        "profile": "review",
        "content": "prior result",
        "session_id": "session-1",
    }]


def test_history_command_rejects_duplicate_stages(tmp_path: Path):
    journal = JournalService(tmp_path)
    for session_id, result_id in (("session-1", "result-1"), ("session-2", "result-2")):
        journal.record_result(
            IntermediateResult(
                id=result_id, session_id=session_id, interaction_id="interaction-1",
                pipeline_id="pipe-1", stage_index=0,
            ),
            result_id,
        )
    with pytest.raises(SystemExit, match="duplicate stage"):
        main(["--data-root", str(tmp_path), "history", "--pipeline-id", "pipe-1", "--json"])
