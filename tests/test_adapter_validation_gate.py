from pathlib import Path

import pytest

from most.models import AIConfiguration, AIRequest, AISession
from most.services import ExecutionManager


class InvalidAdapter:
    def validate_configuration(self, configuration):
        return ["missing required option"]

    def resolve_connectivity(self, configuration):
        raise AssertionError("must validate before resolving endpoint")


def test_manager_validates_adapter_before_network_resolution(tmp_path: Path):
    configuration = AIConfiguration()
    session = AISession()
    request = AIRequest(session_id=session.id, interaction_id="i", configuration_id=configuration.id)
    manager = ExecutionManager(tmp_path)
    execution = manager.prepare(request, configuration, session)
    with pytest.raises(ValueError, match="invalid adapter configuration"):
        manager.execute(execution, request, configuration, InvalidAdapter())
