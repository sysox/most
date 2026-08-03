from pathlib import Path

from most.adapters import Connectivity
from most.models import AIConfiguration, AIRequest, AISession
from most.services import ExecutionManager


class StreamingAdapter:
    def resolve_connectivity(self, configuration):
        return Connectivity("http://localhost", "local", "localhost", "DECLARED")

    def stream(self, request, configuration, credential_handle):
        yield {"event_type": "TextDeltaEvent", "delta": "hello"}
        yield {"event_type": "CompletedEvent"}


def test_stream_events_are_hashed_and_ordered(tmp_path: Path):
    session = AISession()
    configuration = AIConfiguration(adapter_options={"base_url": "http://localhost"})
    request = AIRequest(session_id=session.id, interaction_id="i", configuration_id=configuration.id)
    manager = ExecutionManager(tmp_path)
    execution = manager.prepare(request, configuration, session)
    execution, events = manager.stream(execution, request, configuration, StreamingAdapter())
    assert execution.state.value == "completed"
    assert events[0].sequence_number < events[1].sequence_number
    assert events[1].previous_event_hash == events[0].event_hash
