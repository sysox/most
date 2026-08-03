from pathlib import Path

import pytest

from most.adapters import Connectivity, EffectiveCapabilities
from most.models import AIConfiguration, AIRequest, AISession
from most.services import ExecutionManager


def test_adapter_context_snapshots_are_immutable(tmp_path: Path):
    configuration = AIConfiguration(adapter_options={"base_url": "http://localhost"})
    session = AISession()
    request = AIRequest(session_id=session.id, interaction_id="i", configuration_id=configuration.id)
    manager = ExecutionManager(tmp_path)
    execution = manager.prepare(request, configuration, session)
    context = manager.build_adapter_context(
        execution, request, configuration, Connectivity("http://localhost", "local", "localhost", "DECLARED"),
        EffectiveCapabilities(frozenset({"text_input"})), "opaque", (str(tmp_path),),
    )
    with pytest.raises(TypeError):
        context.request_snapshot["id"] = "changed"
