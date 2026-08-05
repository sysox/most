"""Transparent session journal operations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import AIRequest, IntermediateResult, record_payload
from .persistence import PersistenceCoordinator


def validate_operation_id(value: str) -> str:
    """Validate the identifier before it can cross a header/environment boundary."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("operation_id must be a non-empty string")
    if len(value) > 256:
        raise ValueError("operation_id must be at most 256 characters")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("operation_id must not contain control characters")
    return value


class JournalService:
    def __init__(self, root: Path, application_version: str = "0.2.0"):
        self.store = PersistenceCoordinator(root)
        self.application_version = application_version

    def initialize(self, session_id: str, session_payload: dict[str, object]) -> None:
        self.store.write_yaml(f"sessions/{session_id}/session.yaml", session_payload)

    def record_request(self, session_id: str, request: AIRequest) -> None:
        self.store.write_json(
            f"sessions/{session_id}/structured/request-{request.id}.json",
            record_payload(request, record_type="AI_REQUEST", application_version=self.application_version),
        )

    def record_result(self, result: IntermediateResult, content: str) -> Path:
        relative = f"sessions/{result.session_id}/results/{result.id}.md"
        if (self.store.root / relative).exists():
            raise FileExistsError(f"intermediate result already exists: {result.id}")
        path = self.store._atomic_write(relative, content)
        self.store.write_json(
            f"sessions/{result.session_id}/structured/result-{result.id}.json",
            record_payload(result, record_type="INTERMEDIATE_RESULT", application_version=self.application_version),
        )
        return path

    def record_event(self, session_id: str, event: dict[str, object]) -> None:
        self.store.append_versioned_jsonl(
            f"sessions/{session_id}/events.jsonl", [event],
            record_type="SESSION_EVENT",
        )

    def record_response(self, session_id: str, response_id: str, payload: dict[str, object], secrets: tuple[str, ...] = (),
                        journal_context: dict[str, Any] | None = None) -> Path:
        from .redaction import redact_value
        from .serialization import versioned_payload
        payload = {**payload, **_journal_context(journal_context)}
        return self.store.write_json(
            f"sessions/{session_id}/structured/response-{response_id}.json",
            versioned_payload(redact_value(payload, secrets), record_type="AI_RESPONSE", record_id=response_id),
        )

    def record_error(self, session_id: str, error_id: str, payload: dict[str, object], secrets: tuple[str, ...] = (),
                     journal_context: dict[str, Any] | None = None) -> Path:
        from .redaction import redact_value
        from .serialization import versioned_payload
        payload = {**payload, **_journal_context(journal_context)}
        return self.store.write_json(
            f"sessions/{session_id}/structured/error-{error_id}.json",
            versioned_payload(redact_value(payload, secrets), record_type="ERROR", record_id=error_id),
        )

    def pipeline_history(self, pipeline_id: str) -> list[dict[str, object]]:
        """Return journaled pipeline stages through MOST's public history service."""
        _validate_pipeline_id(pipeline_id)
        stages: dict[int, dict[str, object]] = {}
        sessions_root = self.store.root / "sessions"
        if not sessions_root.is_dir():
            return []
        duplicates: set[int] = set()
        for session_dir in sorted(sessions_root.iterdir(), key=lambda path: path.name):
            if session_dir.is_symlink():
                raise ValueError(f"pipeline history contains a symlinked session: {session_dir.name}")
            structured = session_dir / "structured"
            results_dir = session_dir / "results"
            if structured.is_symlink() or results_dir.is_symlink():
                raise ValueError(f"pipeline history contains a symlinked journal directory: {session_dir.name}")
            if not structured.is_dir():
                continue
            for record_path in sorted(structured.glob("result-*.json"), key=lambda path: path.name):
                if record_path.is_symlink():
                    raise ValueError(f"pipeline history contains a symlinked result record: {record_path.name}")
                try:
                    record = json.loads(record_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError):
                    continue
                if not isinstance(record, dict):
                    continue
                stage_index = record.get("stage_index")
                if (record.get("pipeline_id") != pipeline_id or not isinstance(stage_index, int)
                        or isinstance(stage_index, bool) or stage_index < 0):
                    continue
                result_id = record.get("id")
                if (not isinstance(result_id, str) or not result_id.strip() or result_id in {".", ".."}
                        or "/" in result_id or "\\" in result_id):
                    raise ValueError(f"pipeline history result ID is invalid for {pipeline_id} stage {stage_index}")
                content_path = results_dir / f"{result_id}.md"
                if content_path.is_symlink():
                    raise ValueError(f"pipeline history contains a symlinked result content: {content_path.name}")
                try:
                    content = content_path.read_text(encoding="utf-8")
                except (OSError, UnicodeError) as exc:
                    raise ValueError(
                        f"pipeline history result content is missing for {pipeline_id} stage {stage_index}"
                    ) from exc
                if not content.strip():
                    raise ValueError(f"pipeline history result content is empty for {pipeline_id} stage {stage_index}")
                if stage_index in stages:
                    duplicates.add(stage_index)
                    continue
                operation_id = record.get("operation_id")
                if operation_id is not None:
                    validate_operation_id(operation_id)
                stages[stage_index] = {
                    "stage_index": stage_index,
                    "operation_id": operation_id,
                    "profile": record.get("profile"),
                    "content": content,
                    "session_id": session_dir.name,
                }
        if duplicates:
            duplicate_list = ", ".join(str(index) for index in sorted(duplicates))
            raise ValueError(f"pipeline history is ambiguous for {pipeline_id}; duplicate stage(s): {duplicate_list}")
        return [stages[index] for index in sorted(stages)]


def _journal_context(context: dict[str, Any] | None) -> dict[str, Any]:
    if not context:
        return {}
    unknown = set(context) - {"profile", "pipeline_id", "stage_index", "operation_id"}
    if unknown:
        raise ValueError(f"unknown journal context fields: {sorted(unknown)}")
    result: dict[str, Any] = {}
    for key in ("profile", "pipeline_id", "operation_id"):
        value = context.get(key)
        if value is not None:
            if not isinstance(value, str) or not value:
                raise ValueError(f"journal field {key} must be a non-empty string")
            if key == "operation_id":
                validate_operation_id(value)
            result[key] = value
    stage_index = context.get("stage_index")
    if stage_index is not None:
        if not isinstance(stage_index, int) or isinstance(stage_index, bool) or stage_index < 0:
            raise ValueError("journal field stage_index must be a non-negative integer")
        result["stage_index"] = stage_index
    return result


def _validate_pipeline_id(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("pipeline history requires a non-empty pipeline ID")
    if len(value) > 220 or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("pipeline history pipeline ID contains invalid characters")
    return value
