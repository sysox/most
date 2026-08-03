"""Small application services coordinating domain records and persistence."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .context import assemble_context
from .execution import transition
from .journal import JournalService
from .models import AIConfiguration, AIRequest, AISession, Execution, ExecutionState, IntermediateResult, Interaction, SessionMode, new_id, record_payload, utc_now
from .persistence import PersistenceCoordinator
from .policies import evaluate_exposure, resolve_overflow_policy


class ConfigurationService:
    def __init__(self, root: Path):
        self.store = PersistenceCoordinator(root)

    def save(self, configuration: AIConfiguration) -> Path:
        return self.store.write_yaml(
            f"ai-configurations/{configuration.id}.yaml",
            record_payload(configuration, record_type="AI_CONFIGURATION"),
        )


class SessionService:
    def __init__(self, root: Path):
        self.store = PersistenceCoordinator(root)
        self.journal = JournalService(root)
        self.results: dict[str, IntermediateResult] = {}
        self.sessions: dict[str, AISession] = {}
        self.interactions: dict[str, Interaction] = {}

    def create(self, title: str, mode: SessionMode = SessionMode.COMMUNICATION) -> AISession:
        session = AISession(title=title, mode=mode)
        self.sessions[session.id] = session
        self.journal.initialize(session.id, record_payload(session, record_type="AI_SESSION"))
        return session

    def add_result(self, result: IntermediateResult, content: str) -> IntermediateResult:
        if result.id in self.results:
            raise ValueError(f"result already exists: {result.id}")
        session = self.sessions.get(result.session_id)
        if session is None:
            raise KeyError(f"unknown session {result.session_id}")
        if result.parent_result_id:
            parent = self.results.get(result.parent_result_id)
            if parent is None:
                raise KeyError(f"unknown parent result {result.parent_result_id}")
            if parent.session_id != result.session_id:
                raise ValueError("result parent belongs to another session")
        self.results[result.id] = result
        self.journal.record_result(result, content)
        return result

    def context_for(self, active_result_id: str):
        return assemble_context(active_result_id, self.results)

    def append_interaction(self, session: AISession, configuration_id: str, sequence_number: int) -> Interaction:
        interaction = Interaction(session_id=session.id, sequence_number=sequence_number, configuration_id=configuration_id)
        self.interactions[interaction.id] = interaction
        self.store.append_versioned_jsonl(
            f"sessions/{session.id}/interactions.jsonl", [record_payload(interaction, record_type="INTERACTION")],
            record_type="INTERACTION",
        )
        return interaction

    def create_workspace_from_result(self, source: AISession, result_id: str, title: str | None = None) -> AISession:
        result = self.results.get(result_id)
        if result is None or result.session_id != source.id:
            raise KeyError("result does not belong to source session")
        workspace = self.create(title or source.title, SessionMode.WORKSPACE)
        workspace.origin_session_id = source.id
        workspace.origin_result_id = result_id
        workspace.active_result_id = result_id
        self.journal.initialize(workspace.id, record_payload(workspace, record_type="AI_SESSION"))
        return workspace

    def select_final_result(self, session: AISession, result_id: str) -> AISession:
        result = self.results.get(result_id)
        if result is None or result.session_id != session.id:
            raise KeyError("result does not belong to session")
        for candidate in self.results.values():
            if candidate.session_id == session.id:
                candidate.selected_as_final = candidate.id == result_id
        session.active_result_id = result_id
        session.updated_at = utc_now()
        self.journal.initialize(session.id, record_payload(session, record_type="AI_SESSION"))
        return session


class ExecutionManager:
    def __init__(self, root: Path):
        self.store = PersistenceCoordinator(root)

    def prepare(self, request: AIRequest, configuration: AIConfiguration, session: AISession) -> Execution:
        if not configuration.enabled:
            raise ValueError("configuration is disabled")
        if request.configuration_id != configuration.id:
            raise ValueError("request/configuration mismatch")
        execution = Execution(
            session_id=session.id,
            interaction_id=request.interaction_id,
            request_id=request.id,
            configuration_id=configuration.id,
            configuration_snapshot=record_payload(configuration, record_type="AI_CONFIGURATION"),
        )
        self.store.write_yaml(f"executions/{execution.id}/metadata.yaml", record_payload(execution, record_type="EXECUTION"))
        return execution

    def validate_connectivity(self, execution: Execution, *, resolved_location: str, resolved_network: str | None,
                              confirmation: bool = False) -> Execution:
        configuration = execution.configuration_snapshot
        resolution = evaluate_exposure(configuration["location"], configuration.get("network"), resolved_location, resolved_network, confirmation=confirmation)
        if resolution.action.value == "FAIL":
            raise PermissionError(resolution.reason)
        return replace(execution, resolved_connectivity={"location": resolved_location, "network": resolved_network, "action": resolution.action.value})

    def start(self, execution: Execution) -> Execution:
        execution, event = transition(execution, ExecutionState.VALIDATING)
        self.store.append_jsonl(f"executions/{execution.id}/events.jsonl", [event])
        execution, event = transition(execution, ExecutionState.READY)
        self.store.append_jsonl(f"executions/{execution.id}/events.jsonl", [event])
        self.store.write_yaml(f"executions/{execution.id}/metadata.yaml", record_payload(execution, record_type="EXECUTION"))
        return execution

    def execute(self, execution: Execution, request: AIRequest, configuration: AIConfiguration, adapter,
                credential_handle: str | None = None, confirmation: bool = False):
        """Run one adapter invocation only after connectivity/exposure validation."""
        connectivity = adapter.resolve_connectivity(record_payload(configuration, record_type="AI_CONFIGURATION"))
        execution = self.validate_connectivity(
            execution,
            resolved_location=connectivity.location,
            resolved_network=connectivity.network,
            confirmation=confirmation,
        )
        execution, event = transition(execution, ExecutionState.VALIDATING)
        self._event(execution, event)
        execution, event = transition(execution, ExecutionState.READY)
        self._event(execution, event)
        execution, event = transition(execution, ExecutionState.STARTING)
        self._event(execution, event)
        execution, event = transition(execution, ExecutionState.RUNNING)
        self._event(execution, event)
        try:
            response = adapter.execute(record_payload(request, record_type="AI_REQUEST"), record_payload(configuration, record_type="AI_CONFIGURATION"), credential_handle)
            execution, event = transition(execution, ExecutionState.COMPLETED)
            self._event(execution, event)
            return execution, response
        except Exception as exc:
            failed = replace(execution, error={"type": type(exc).__name__, "message": str(exc)})
            failed, event = transition(failed, ExecutionState.FAILED)
            self._event(failed, event)
            self.store.write_yaml(f"executions/{failed.id}/metadata.yaml", record_payload(failed, record_type="EXECUTION"))
            raise

    def _event(self, execution: Execution, event: dict[str, object]) -> None:
        existing = self.store.read_jsonl(f"executions/{execution.id}/events.jsonl")
        event = {
            "event_id": new_id(),
            "execution_id": execution.id,
            "sequence_number": len(existing) + 1,
            "event_type": "StatusEvent",
            "observation_source": "PROCESS_METADATA",
            **event,
        }
        self.store.append_versioned_jsonl(
            f"executions/{execution.id}/events.jsonl", [event],
            record_type="STATUS_EVENT",
        )
        self.store.write_yaml(f"executions/{execution.id}/metadata.yaml", record_payload(execution, record_type="EXECUTION"))
