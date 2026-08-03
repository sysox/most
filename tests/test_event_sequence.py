from pathlib import Path

from most.adapters import Connectivity
from most.models import AIConfiguration, AIRequest, AISession
from most.persistence import PersistenceCoordinator
from most.services import ExecutionManager


class Adapter:
    def resolve_connectivity(self, configuration):
        return Connectivity("http://localhost", "local", "localhost", "DECLARED")

    def execute(self, request, configuration, credential_handle):
        return {"ok": True}


def test_execution_events_have_monotonic_sequence_numbers(tmp_path: Path):
    configuration = AIConfiguration(adapter_options={"base_url": "http://localhost"})
    session = AISession()
    request = AIRequest(session_id=session.id, interaction_id="i", configuration_id=configuration.id)
    manager = ExecutionManager(tmp_path)
    execution = manager.prepare(request, configuration, session)
    manager.execute(execution, request, configuration, Adapter())
    events = PersistenceCoordinator(tmp_path).read_jsonl(f"executions/{execution.id}/events.jsonl")
    assert [event["sequence_number"] for event in events] == list(range(1, len(events) + 1))
