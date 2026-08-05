"""Portable domain records and canonical persistence headers."""

from __future__ import annotations

import secrets
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


def new_id() -> str:
    """Return a sortable UUIDv7 identifier without an external dependency."""
    timestamp_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    random_a = secrets.randbits(12)
    random_b = secrets.randbits(62)
    value = (timestamp_ms << 80) | (0x7 << 76) | (random_a << 64) | (0x2 << 62) | random_b
    return str(uuid.UUID(int=value))


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class SessionMode(str, Enum):
    COMMUNICATION = "COMMUNICATION"
    WORKSPACE = "WORKSPACE"


class ExecutionState(str, Enum):
    CREATED = "created"
    VALIDATING = "validating"
    READY = "ready"
    STARTING = "starting"
    RUNNING = "running"
    STREAMING = "streaming"
    WAITING_FOR_USER = "waiting_for_user"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class OverflowPolicy(str, Enum):
    FAIL = "FAIL"
    TRIM_OLDEST = "TRIM_OLDEST"
    SUMMARIZE_WITH_CONFIRMATION = "SUMMARIZE_WITH_CONFIRMATION"
    SELECT_MANUALLY = "SELECT_MANUALLY"


class ExposureAction(str, Enum):
    FAIL = "FAIL"
    REQUIRE_CONFIRMATION = "REQUIRE_CONFIRMATION"
    ALLOW_BY_POLICY = "ALLOW_BY_POLICY"


@dataclass(slots=True)
class AIProvider:
    id: str = field(default_factory=new_id)
    name: str = ""
    description: str = ""
    website: str | None = None
    provider_type: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AIModel:
    id: str = field(default_factory=new_id)
    provider_id: str = ""
    model_name: str = ""
    display_name: str = ""
    version: str | None = None
    context_limit: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AccessMethod:
    id: str = field(default_factory=new_id)
    type: str = ""
    adapter_type: str = ""
    display_name: str = ""
    configuration_schema: dict[str, Any] = field(default_factory=dict)
    supported_features: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ContextAssemblyRecord:
    id: str = field(default_factory=new_id)
    session_id: str = ""
    interaction_id: str = ""
    active_result_id: str | None = None
    lineage_result_ids: list[str] = field(default_factory=list)
    included_message_ids: list[str] = field(default_factory=list)
    included_attachment_ids: list[str] = field(default_factory=list)
    excluded_result_ids: list[str] = field(default_factory=list)
    excluded_message_ids: list[str] = field(default_factory=list)
    transformations: list[str] = field(default_factory=list)
    workspace_context_strategy: str = "EXPLICIT_SELECTION"
    token_estimate: int = 0
    token_limit: int | None = None
    overflow_policy: OverflowPolicy = OverflowPolicy.FAIL
    created_at: str = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Message:
    id: str = field(default_factory=new_id)
    role: str = "user"
    content_parts: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Interaction:
    id: str = field(default_factory=new_id)
    session_id: str = ""
    sequence_number: int = 0
    configuration_id: str = ""
    request_id: str | None = None
    execution_id: str | None = None
    created_at: str = field(default_factory=utc_now)
    status: str = "created"


@dataclass(slots=True)
class AIResponse:
    id: str = field(default_factory=new_id)
    request_id: str = ""
    configuration_id: str = ""
    content_parts: list[dict[str, Any]] = field(default_factory=list)
    finish_status: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    cost: dict[str, Any] | None = None
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    profile: str | None = None
    pipeline_id: str | None = None
    stage_index: int | None = None
    raw_response_reference: str | None = None
    created_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class ApplicationSettings:
    application_instance_id: str = field(default_factory=new_id)
    default_exposure_transition_policy_reference: str | None = None
    default_context_overflow_policy: OverflowPolicy = OverflowPolicy.FAIL
    default_workspace_context_strategy: str = "EXPLICIT_SELECTION"
    application_data_root: str = "application-data"
    browser_profile_root: str = "browser-profiles"
    temporary_workspace_root: str = "temporary-workspaces"
    artifact_root: str = "artifacts"
    default_logging_policy: dict[str, Any] = field(default_factory=dict)
    lease_timeout_seconds: int = 300
    process_cancel_grace_seconds: int = 5
    event_flush_interval_ms: int = 100
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class AIIteration:
    id: str = field(default_factory=new_id)
    session_id: str = ""
    interaction_id: str = ""
    request_id: str = ""
    execution_id: str = ""
    sequence_number: int = 0
    input_result_id: str | None = None
    intermediate_result_ids: list[str] = field(default_factory=list)
    base_commit: str | None = None
    resulting_commit: str | None = None
    changed_files: list[str] = field(default_factory=list)
    proposed_patch_reference: str | None = None
    final_diff_reference: str | None = None
    commands_log_reference: str | None = None
    tests_log_reference: str | None = None
    review_results_reference: str | None = None
    status: str = "created"
    created_at: str = field(default_factory=utc_now)
    completed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PersistedRecordHeader:
    schema_version: int
    record_type: str
    record_id: str
    written_at: str
    writer_application_version: str

    def __post_init__(self) -> None:
        if self.schema_version < 1:
            raise ValueError("schema_version must be positive")
        if not self.record_type or not self.record_id:
            raise ValueError("record_type and record_id are required")


@dataclass(slots=True)
class AIConfiguration:
    id: str = field(default_factory=new_id)
    name: str = ""
    provider_id: str = ""
    model_reference: str | None = None
    access_method_id: str = ""
    credential_reference: str | None = None
    location: str = "local"
    network: str | None = None
    exposure_transition_policy_reference: str | None = None
    context_overflow_policy: OverflowPolicy = OverflowPolicy.FAIL
    workspace_context_strategy: str = "EXPLICIT_SELECTION"
    privacy_policy: dict[str, Any] = field(default_factory=dict)
    logging_policy: dict[str, Any] = field(default_factory=dict)
    adapter_options: dict[str, Any] = field(default_factory=dict)
    declared_capabilities: list[str] = field(default_factory=list)
    enabled: bool = True


@dataclass(slots=True)
class AISession:
    id: str = field(default_factory=new_id)
    title: str = ""
    mode: SessionMode = SessionMode.COMMUNICATION
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    default_configuration_id: str | None = None
    workspace_id: str | None = None
    active_result_id: str | None = None
    origin_session_id: str | None = None
    origin_result_id: str | None = None
    status: str = "active"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class IntermediateResult:
    id: str = field(default_factory=new_id)
    session_id: str = ""
    interaction_id: str = ""
    execution_id: str | None = None
    sequence_number: int = 0
    result_type: str = "draft"
    content_reference: str | None = None
    structured_reference: str | None = None
    parent_result_id: str | None = None
    selected_as_final: bool = False
    profile: str | None = None
    pipeline_id: str | None = None
    stage_index: int | None = None
    created_at: str = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AIRequest:
    id: str = field(default_factory=new_id)
    session_id: str = ""
    interaction_id: str = ""
    configuration_id: str = ""
    messages: list[dict[str, Any]] = field(default_factory=list)
    attachments: list[str] = field(default_factory=list)
    generation_options: dict[str, Any] = field(default_factory=dict)
    execution_options: dict[str, Any] = field(default_factory=dict)
    profile: str | None = None
    pipeline_id: str | None = None
    stage_index: int | None = None
    created_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class Execution:
    id: str = field(default_factory=new_id)
    session_id: str = ""
    interaction_id: str = ""
    request_id: str = ""
    configuration_id: str = ""
    state: ExecutionState = ExecutionState.CREATED
    waiting_reason: str | None = None
    configuration_snapshot: dict[str, Any] = field(default_factory=dict)
    resolved_connectivity: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    error: dict[str, Any] | None = None


@dataclass(slots=True)
class ExecutionStep:
    id: str = field(default_factory=new_id)
    execution_id: str = ""
    sequence_number: int = 0
    step_type: str = "external_agent_run"
    status: str = "started"
    started_at: str = field(default_factory=utc_now)
    finished_at: str | None = None
    input_reference: str | None = None
    output_reference: str | None = None
    intermediate_result_id: str | None = None
    observation_source: str = "PROCESS_METADATA"
    observation_confidence: str = "observed"
    metadata: dict[str, Any] = field(default_factory=dict)


def record_payload(record: Any, *, record_type: str, application_version: str = "0.1.0") -> dict[str, Any]:
    data = asdict(record)
    def normalize(value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return value
    data = normalize(data)
    record_id = getattr(record, "id", None) or getattr(record, "application_instance_id", None)
    if not record_id:
        raise ValueError("record must expose id or application_instance_id")
    header = PersistedRecordHeader(1, record_type, record_id, utc_now(), application_version)
    return {**asdict(header), **data}
