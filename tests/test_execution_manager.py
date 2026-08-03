from pathlib import Path

from most.adapters import Connectivity, Observability
from most.models import AIConfiguration, AIRequest, AISession
from most.services import ExecutionManager


class FakeAdapter:
    def validate_configuration(self, configuration):
        return []

    def resolve_connectivity(self, configuration):
        return Connectivity(configuration["adapter_options"]["base_url"], "local", "localhost", "DECLARED")

    def get_observability_profile(self, configuration):
        return Observability.BLOCK

    def execute(self, request, configuration, credential_handle):
        return {"credential_received": credential_handle is not None, "request": request["id"]}


def test_execution_manager_checks_then_runs_adapter(tmp_path: Path):
    configuration = AIConfiguration(name="local", adapter_options={"base_url": "http://localhost"})
    session = AISession()
    request = AIRequest(session_id=session.id, interaction_id="i", configuration_id=configuration.id)
    manager = ExecutionManager(tmp_path)
    execution = manager.prepare(request, configuration, session)
    execution, response = manager.execute(execution, request, configuration, FakeAdapter(), "opaque")
    assert execution.state.value == "completed"
    assert response["credential_received"]
