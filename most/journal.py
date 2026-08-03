"""Transparent session journal operations."""

from __future__ import annotations

from pathlib import Path

from .models import AIRequest, IntermediateResult, record_payload
from .persistence import PersistenceCoordinator


class JournalService:
    def __init__(self, root: Path, application_version: str = "0.1.0"):
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
        path = self.store._atomic_write(relative, content)
        self.store.write_json(
            f"sessions/{result.session_id}/structured/result-{result.id}.json",
            record_payload(result, record_type="INTERMEDIATE_RESULT", application_version=self.application_version),
        )
        return path

    def record_event(self, session_id: str, event: dict[str, object]) -> None:
        self.store.append_jsonl(f"sessions/{session_id}/events.jsonl", [event])
