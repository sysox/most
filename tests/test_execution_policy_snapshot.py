from pathlib import Path

from most.models import AIConfiguration, AIRequest, AISession, OverflowPolicy
from most.services import ExecutionManager


def test_execution_snapshots_resolved_policy_sources(tmp_path: Path):
    configuration = AIConfiguration(name="n", provider_id="p", access_method_id="a")
    request = AIRequest(
        session_id="s", interaction_id="i", configuration_id=configuration.id,
        execution_options={"context_overflow_policy": "TRIM_OLDEST"},
    )
    execution = ExecutionManager(tmp_path).prepare(request, configuration, AISession(id="s"))
    policies = execution.configuration_snapshot["resolved_policies"]
    assert policies["context_overflow_policy"] == OverflowPolicy.TRIM_OLDEST.value
    assert policies["sources"]["overflow"] == "request_override"
