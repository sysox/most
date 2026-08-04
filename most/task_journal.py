"""Journal records for one-shot non-chat operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import AIConfiguration, AIRequest, IntermediateResult, new_id
from .services import ConfigurationService, SessionService


def record_task(root: Path, *, provider: str, model: str, operation: str, input_summary: str,
                output_summary: str, metadata: dict[str, Any] | None = None) -> str:
    sessions = SessionService(root)
    session = sessions.create(f"{provider} {operation}: {model}")
    configuration = AIConfiguration(
        name=f"{provider}: {model}", provider_id=provider, access_method_id="api",
        model_reference=model, location="provider-cloud", network="public-internet",
    )
    ConfigurationService(root).save(configuration)
    interaction = sessions.append_interaction(session, configuration.id, 1)
    request = AIRequest(
        session_id=session.id, interaction_id=interaction.id, configuration_id=configuration.id,
        messages=[{"role": "user", "content": input_summary}],
        execution_options={"operation": operation},
    )
    sessions.journal.record_request(session.id, request)
    result = IntermediateResult(
        session_id=session.id, interaction_id=interaction.id, execution_id=None,
        sequence_number=1, result_type=operation, metadata=metadata or {},
    )
    sessions.add_result(result, output_summary)
    sessions.journal.record_response(session.id, new_id(), {"operation": operation, **(metadata or {})})
    return session.id
