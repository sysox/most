"""Small application services coordinating domain records and persistence."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .adapters import (
    AdapterExecutionContext,
    AdapterRegistry,
    Connectivity,
    EffectiveCapabilities,
    immutable_snapshot,
)
from .context import apply_overflow_policy, assemble_context, estimate_tokens
from .events import StreamEvent, create_stream_event
from .execution import transition
from .journal import JournalService
from .models import (
    AIConfiguration,
    AIRequest,
    AISession,
    ContextAssemblyRecord,
    Execution,
    ExecutionState,
    ExecutionStep,
    Interaction,
    IntermediateResult,
    SessionMode,
    new_id,
    record_payload,
    utc_now,
)
from .network import NetworkInspector
from .persistence import PersistenceCoordinator
from .policies import PolicyOverrides, evaluate_exposure, resolve_policies
from .schemas import require_valid_ai_configuration
from .workspace_context import WorkspaceContextSelector


class SettingsService:
    def __init__(self, root: Path):
        self.store = PersistenceCoordinator(root)

    def initialize(self, settings=None):
        from .models import ApplicationSettings
        settings = settings or ApplicationSettings(application_data_root=str(self.store.root))
        self.store.write_yaml("app-config.yaml", record_payload(settings, record_type="APPLICATION_SETTINGS"))
        return settings

    def load(self) -> dict[str, object] | None:
        import yaml
        path = self.store.root / "app-config.yaml"
        if not path.exists():
            return None
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None


class ConfigurationService:
    def __init__(self, root: Path):
        self.store = PersistenceCoordinator(root)

    def save(self, configuration: AIConfiguration) -> Path:
        payload = record_payload(configuration, record_type="AI_CONFIGURATION")
        require_valid_ai_configuration(payload)
        return self.store.write_yaml(
            f"ai-configurations/{configuration.id}.yaml",
            payload,
        )

    def get(self, configuration_id: str) -> dict[str, object] | None:
        import yaml
        path = self.store.root / "ai-configurations" / f"{configuration_id}.yaml"
        if not path.exists():
            return None
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None

    def list(self) -> list[dict[str, object]]:
        return [value for value in (self.get(path.stem) for path in (self.store.root / "ai-configurations").glob("*.yaml")) if value]


class ConnectivityService:
    def __init__(self, registry: AdapterRegistry, network_inspector):
        self.registry = registry
        self.network_inspector = network_inspector

    def resolve(self, adapter_type: str, configuration: dict[str, object]) -> Connectivity:
        adapter_resolution = self.registry.get(adapter_type).resolve_connectivity(configuration)
        endpoint = adapter_resolution.endpoint
        if not endpoint:
            return adapter_resolution
        return self.network_inspector.inspect(endpoint, adapter_resolution.location, adapter_resolution.network)


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

    def list(self) -> list[dict[str, object]]:
        import yaml
        directory = self.store.root / "sessions"
        records = []
        for path in sorted(directory.glob("*/session.yaml")):
            value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(value, dict):
                records.append(value)
        return records

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

    def assemble_request_context(
        self,
        session: AISession,
        interaction_id: str,
        active_result_id: str,
        messages: list[dict[str, object]],
        configuration: AIConfiguration,
        token_limit: int,
        reserved_output_tokens: int = 0,
        workspace_repository: Path | None = None,
        workspace_paths: tuple[str, ...] = (),
    ) -> tuple[list[dict[str, object]], ContextAssemblyRecord]:
        assembly = assemble_context(active_result_id, self.results)
        source_selection = None
        source_messages: list[dict[str, object]] = []
        if workspace_repository is not None:
            options = configuration.adapter_options.get("workspace_context", {})
            if not isinstance(options, dict):
                raise ValueError("workspace_context options must be a mapping")
            selector = WorkspaceContextSelector(workspace_repository)
            source_selection = selector.select(
                configuration.workspace_context_strategy,
                explicit_paths=workspace_paths,
                include_patterns=tuple(str(value) for value in options.get("include_patterns", ())),
                exclude_patterns=tuple(str(value) for value in options.get("exclude_patterns", ())),
                include_git_diff=bool(options.get("include_git_diff", False)),
                max_files=int(options["max_files"]) if options.get("max_files") is not None else None,
                max_bytes=int(options["max_bytes"]) if options.get("max_bytes") is not None else None,
            )
            source_messages = [
                {"role": "system", "content": f"[workspace file: {item.path}]\n{item.content}"}
                for item in source_selection.files
            ]
            if source_selection.git_diff:
                source_messages.append({"role": "system", "content": f"[workspace git diff]\n{source_selection.git_diff}"})
        combined_messages = source_messages + messages
        selected, transformation = apply_overflow_policy(
            combined_messages,
            token_limit=token_limit,
            policy=configuration.context_overflow_policy,
            reserved_output_tokens=reserved_output_tokens,
            pinned_indices=set(range(len(source_messages))),
        )
        metadata: dict[str, object] = {}
        if source_selection is not None:
            metadata["workspace_files"] = [
                {"path": item.path, "sha256": item.sha256, "size": item.size}
                for item in source_selection.files
            ]
            metadata["workspace_excluded_paths"] = list(source_selection.excluded_paths)
            metadata["workspace_git_diff_included"] = source_selection.git_diff is not None
        record = ContextAssemblyRecord(
            session_id=session.id,
            interaction_id=interaction_id,
            active_result_id=active_result_id,
            lineage_result_ids=list(assembly.lineage_result_ids),
            excluded_result_ids=list(assembly.excluded_result_ids),
            transformations=list(assembly.transformations) + [transformation],
            workspace_context_strategy=configuration.workspace_context_strategy,
            token_estimate=estimate_tokens(selected) + reserved_output_tokens,
            token_limit=token_limit,
            overflow_policy=configuration.context_overflow_policy,
            metadata=metadata,
        )
        self.store.write_json(
            f"sessions/{session.id}/structured/context-{record.id}.json",
            record_payload(record, record_type="CONTEXT_ASSEMBLY"),
        )
        return selected, record

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
    def __init__(self, root: Path, network_inspector: NetworkInspector | None = None):
        self.store = PersistenceCoordinator(root)
        self.journal = JournalService(root)
        self.network_inspector = network_inspector or NetworkInspector()

    def prepare(self, request: AIRequest, configuration: AIConfiguration, session: AISession) -> Execution:
        if not configuration.enabled:
            raise ValueError("configuration is disabled")
        if request.configuration_id != configuration.id:
            raise ValueError("request/configuration mismatch")
        configuration_payload = record_payload(configuration, record_type="AI_CONFIGURATION")
        request_overrides = request.execution_options
        overrides = PolicyOverrides(
            exposure_policy_reference=request_overrides.get("exposure_policy_reference"),
            context_overflow_policy=request_overrides.get("context_overflow_policy"),
            workspace_context_strategy=request_overrides.get("workspace_context_strategy"),
            explicit_exposure_override=bool(request_overrides.get("explicit_exposure_override", False)),
        )
        policies = resolve_policies(configuration_payload, overrides=overrides)
        configuration_payload["resolved_policies"] = {
            "exposure_policy_reference": policies.exposure_policy_reference,
            "context_overflow_policy": policies.overflow_policy.value,
            "workspace_context_strategy": policies.workspace_context_strategy,
            "sources": policies.sources,
        }
        execution = Execution(
            session_id=session.id,
            interaction_id=request.interaction_id,
            request_id=request.id,
            configuration_id=configuration.id,
            configuration_snapshot=configuration_payload,
        )
        self.store.write_yaml(f"executions/{execution.id}/metadata.yaml", record_payload(execution, record_type="EXECUTION"))
        return execution

    def record_step(self, execution: Execution, step: ExecutionStep) -> ExecutionStep:
        if step.execution_id != execution.id:
            raise ValueError("execution step belongs to another execution")
        existing = self.store.read_jsonl(f"executions/{execution.id}/steps.jsonl")
        step.sequence_number = len(existing) + 1
        self.store.append_versioned_jsonl(
            f"executions/{execution.id}/steps.jsonl",
            [record_payload(step, record_type="EXECUTION_STEP")],
            record_type="EXECUTION_STEP",
        )
        return step

    def build_adapter_context(self, execution: Execution, request: AIRequest, configuration: AIConfiguration,
                              connectivity: Connectivity, capabilities: EffectiveCapabilities,
                              credential_handle: str | None = None, workspace_scope: tuple[str, ...] = ()) -> AdapterExecutionContext:
        return AdapterExecutionContext(
            execution_id=execution.id,
            request_snapshot=immutable_snapshot(record_payload(request, record_type="AI_REQUEST")),
            configuration_snapshot=immutable_snapshot(record_payload(configuration, record_type="AI_CONFIGURATION")),
            effective_capabilities=capabilities,
            context_assembly_record=immutable_snapshot({}),
            resolved_connectivity=connectivity,
            credential_handle=credential_handle,
            workspace_scope=workspace_scope,
        )

    def validate_connectivity(self, execution: Execution, *, resolved_location: str, resolved_network: str | None,
                              confirmation: bool = False, resolved_confidence: str | None = None,
                              evidence: tuple[str, ...] = ()) -> Execution:
        configuration = execution.configuration_snapshot
        resolution = evaluate_exposure(
            configuration["location"], configuration.get("network"), resolved_location, resolved_network,
            confirmation=confirmation, resolved_confidence=resolved_confidence,
        )
        if resolution.action.value == "FAIL":
            raise PermissionError(resolution.reason)
        return replace(execution, resolved_connectivity={
            "location": resolved_location, "network": resolved_network,
            "confidence": resolved_confidence, "evidence": list(evidence),
            "action": resolution.action.value,
        })

    def start(self, execution: Execution) -> Execution:
        execution, event = transition(execution, ExecutionState.VALIDATING)
        self._event(execution, event)
        execution, event = transition(execution, ExecutionState.READY)
        self._event(execution, event)
        return execution

    def execute(self, execution: Execution, request: AIRequest, configuration: AIConfiguration, adapter,
                credential_handle: str | None = None, confirmation: bool = False):
        """Run one adapter invocation only after connectivity/exposure validation."""
        self._validate_adapter_configuration(adapter, configuration)
        declared_connectivity = adapter.resolve_connectivity(record_payload(configuration, record_type="AI_CONFIGURATION"))
        connectivity = declared_connectivity
        if declared_connectivity.endpoint:
            connectivity = self.network_inspector.inspect(
                declared_connectivity.endpoint,
                declared_connectivity.location,
                declared_connectivity.network,
            )
        execution = self.validate_connectivity(
            execution,
            resolved_location=connectivity.location,
            resolved_network=connectivity.network,
            confirmation=confirmation,
            resolved_confidence=connectivity.confidence,
            evidence=connectivity.evidence,
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
            self.journal.record_request(execution.session_id, request)
            response = adapter.execute(record_payload(request, record_type="AI_REQUEST"), record_payload(configuration, record_type="AI_CONFIGURATION"), credential_handle)
            self.journal.record_response(
                execution.session_id,
                new_id(),
                _response_payload(response),
            )
            execution, event = transition(execution, ExecutionState.COMPLETED)
            self._event(execution, event)
            return execution, response
        except Exception as exc:
            self.journal.record_error(
                execution.session_id,
                new_id(),
                {"execution_id": execution.id, "type": type(exc).__name__, "message": str(exc)},
            )
            failed = replace(execution, error={"type": type(exc).__name__, "message": str(exc)})
            failed, event = transition(failed, ExecutionState.FAILED)
            self._event(failed, event)
            self.store.write_yaml(f"executions/{failed.id}/metadata.yaml", record_payload(failed, record_type="EXECUTION"))
            raise

    def stream(self, execution: Execution, request: AIRequest, configuration: AIConfiguration, adapter,
               credential_handle: str | None = None, confirmation: bool = False) -> tuple[Execution, list[StreamEvent]]:
        """Run a structured adapter stream and persist every observed event."""
        self._validate_adapter_configuration(adapter, configuration)
        declared = adapter.resolve_connectivity(record_payload(configuration, record_type="AI_CONFIGURATION"))
        connectivity = declared
        if declared.endpoint:
            connectivity = self.network_inspector.inspect(declared.endpoint, declared.location, declared.network)
        execution = self.validate_connectivity(
            execution,
            resolved_location=connectivity.location,
            resolved_network=connectivity.network,
            confirmation=confirmation,
            resolved_confidence=connectivity.confidence,
            evidence=connectivity.evidence,
        )
        for target in (ExecutionState.VALIDATING, ExecutionState.READY, ExecutionState.STARTING, ExecutionState.RUNNING, ExecutionState.STREAMING):
            execution, status_event = transition(execution, target)
            self._event(execution, status_event)
        observed: list[StreamEvent] = []
        previous_hash = None
        try:
            self.journal.record_request(execution.session_id, request)
            for item in adapter.stream(record_payload(request, record_type="AI_REQUEST"), record_payload(configuration, record_type="AI_CONFIGURATION"), credential_handle):
                event = create_stream_event(
                    execution.id,
                    len(self.store.read_jsonl(f"executions/{execution.id}/events.jsonl")) + 1,
                    str(item.get("event_type", "TextDeltaEvent")),
                    dict(item),
                    str(item.get("observation_source", "PROVIDER_EVENT")),
                    previous_hash,
                )
                observed.append(event)
                previous_hash = event.event_hash
                self.store.append_versioned_jsonl(
                    f"executions/{execution.id}/events.jsonl", [event.__dict__ if hasattr(event, "__dict__") else {
                        "event_id": event.event_id, "execution_id": event.execution_id,
                        "sequence_number": event.sequence_number, "event_type": event.event_type,
                        "created_at": event.created_at, "observation_source": event.observation_source,
                        "payload": event.payload, "previous_event_hash": event.previous_event_hash,
                        "event_hash": event.event_hash,
                    }], record_type="STREAM_EVENT",
                )
            self.journal.record_response(
                execution.session_id,
                new_id(),
                {"execution_id": execution.id, "stream_events": [event.payload for event in observed]},
            )
            execution, status_event = transition(execution, ExecutionState.COMPLETED)
            self._event(execution, status_event)
            return execution, observed
        except Exception as exc:
            self.journal.record_error(
                execution.session_id,
                new_id(),
                {"execution_id": execution.id, "type": type(exc).__name__, "message": str(exc)},
            )
            failed = replace(execution, error={"type": type(exc).__name__, "message": str(exc)})
            failed, status_event = transition(failed, ExecutionState.FAILED)
            self._event(failed, status_event)
            raise

    def cancel(self, execution: Execution, reason: str = "user_requested") -> Execution:
        if execution.state in {ExecutionState.COMPLETED, ExecutionState.FAILED, ExecutionState.CANCELLED}:
            return execution
        execution, event = transition(execution, ExecutionState.CANCELLED, reason=reason)
        self._event(execution, event)
        return execution

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
        if execution.state in {ExecutionState.COMPLETED, ExecutionState.FAILED, ExecutionState.CANCELLED}:
            from .serialization import versioned_payload
            self.store.write_json(
                f"executions/{execution.id}/completion.json",
                versioned_payload(
                    {"execution_id": execution.id, "state": execution.state.value, "completed_at": execution.updated_at},
                    record_type="EXECUTION_COMPLETION", record_id=execution.id,
                ),
            )

    @staticmethod
    def _validate_adapter_configuration(adapter, configuration: AIConfiguration) -> None:
        validate = getattr(adapter, "validate_configuration", None)
        if validate is None:
            raise TypeError("adapter must implement validate_configuration")
        errors = validate(record_payload(configuration, record_type="AI_CONFIGURATION"))
        if errors:
            raise ValueError("invalid adapter configuration: " + "; ".join(str(error) for error in errors))


def _response_payload(response: object) -> dict[str, object]:
    """Convert adapter responses to a redacted-journal-friendly mapping."""
    if isinstance(response, dict):
        return response
    body = getattr(response, "body", None)
    status = getattr(response, "status", None)
    if isinstance(body, dict):
        return {"status": status, "body": body}
    return {"value": str(response)}
