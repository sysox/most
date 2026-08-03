"""Small application services coordinating domain records and persistence."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .context import assemble_context
from .execution import transition
from .journal import JournalService
from .models import AIConfiguration, AIRequest, AISession, Execution, ExecutionState, IntermediateResult, SessionMode, record_payload
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

    def create(self, title: str, mode: SessionMode = SessionMode.COMMUNICATION) -> AISession:
        session = AISession(title=title, mode=mode)
        self.journal.initialize(session.id, record_payload(session, record_type="AI_SESSION"))
        return session

    def add_result(self, result: IntermediateResult, content: str) -> IntermediateResult:
        if result.id in self.results:
            raise ValueError(f"result already exists: {result.id}")
        self.results[result.id] = result
        self.journal.record_result(result, content)
        return result

    def context_for(self, active_result_id: str):
        return assemble_context(active_result_id, self.results)


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
        self.store.append_versioned_jsonl(
            f"executions/{execution.id}/events.jsonl", [event],
            record_type="STATUS_EVENT",
        )
        self.store.write_yaml(f"executions/{execution.id}/metadata.yaml", record_payload(execution, record_type="EXECUTION"))
