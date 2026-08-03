from pathlib import Path

from most.models import AIConfiguration, AIRequest, AISession, ExecutionStep
from most.services import ExecutionManager


def test_execution_steps_record_only_observed_detail(tmp_path: Path):
    session = AISession()
    configuration = AIConfiguration()
    request = AIRequest(session_id=session.id, interaction_id="i", configuration_id=configuration.id)
    manager = ExecutionManager(tmp_path)
    execution = manager.prepare(request, configuration, session)
    step = manager.record_step(execution, ExecutionStep(execution_id=execution.id, step_type="external_agent_run", observation_source="PROCESS_METADATA"))
    assert step.sequence_number == 1
    assert step.observation_source == "PROCESS_METADATA"
