from pathlib import Path

from most.models import AIConfiguration, AIRequest, AISession, ExecutionState
from most.services import ExecutionManager


def test_cancelled_execution_has_completion_marker(tmp_path: Path):
    session = AISession()
    configuration = AIConfiguration()
    request = AIRequest(session_id=session.id, interaction_id="i", configuration_id=configuration.id)
    manager = ExecutionManager(tmp_path)
    execution = manager.prepare(request, configuration, session)
    execution = manager.start(execution)
    execution = manager.cancel(execution)
    assert execution.state is ExecutionState.CANCELLED
    assert (tmp_path / "executions" / execution.id / "completion.json").exists()
