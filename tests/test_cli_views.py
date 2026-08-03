import json
from pathlib import Path

from most.cli import main
from most.models import AIConfiguration, AIRequest, AISession
from most.services import ExecutionManager


def test_cli_inspects_execution_events(tmp_path: Path, capsys):
    session = AISession()
    configuration = AIConfiguration()
    request = AIRequest(session_id=session.id, interaction_id="i", configuration_id=configuration.id)
    execution = ExecutionManager(tmp_path).prepare(request, configuration, session)
    assert main(["--data-root", str(tmp_path), "inspect-execution", execution.id]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["metadata"]["record_type"] == "EXECUTION"
