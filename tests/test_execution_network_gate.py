from pathlib import Path

import pytest

from most.adapters import Connectivity
from most.models import AIConfiguration, AIRequest, AISession
from most.services import ExecutionManager


class UnknownAdapter:
    def validate_configuration(self, configuration):
        return []

    def resolve_connectivity(self, configuration):
        return Connectivity("https://unresolvable.invalid", "local", "localhost", "DECLARED")

    def execute(self, request, configuration, credential_handle):
        raise AssertionError("must not transmit")


def test_execution_manager_inspects_endpoint_before_transmission(tmp_path: Path):
    configuration = AIConfiguration(adapter_options={"base_url": "https://unresolvable.invalid"})
    session = AISession()
    request = AIRequest(session_id=session.id, interaction_id="i", configuration_id=configuration.id)
    manager = ExecutionManager(tmp_path)
    execution = manager.prepare(request, configuration, session)
    with pytest.raises(PermissionError, match="unknown connectivity"):
        manager.execute(execution, request, configuration, UnknownAdapter())
