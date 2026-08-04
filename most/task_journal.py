"""Journal records for one-shot non-chat operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import AIConfiguration, AIRequest, IntermediateResult, new_id
from .services import ConfigurationService, SessionService


def record_task(root: Path, *, provider: str, model: str, operation: str, input_summary: str,
                output_summary: str, metadata: dict[str, Any] | None = None,
                pricing: dict[str, Any] | None = None) -> str:
    task_metadata = dict(metadata or {})
    cost = estimate_cost(task_metadata.get("usage"), pricing)
    if cost is not None:
        task_metadata["estimated_cost_usd"] = cost
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
        sequence_number=1, result_type=operation, metadata=task_metadata,
    )
    sessions.add_result(result, output_summary)
    sessions.journal.record_response(session.id, new_id(), {"operation": operation, **task_metadata})
    return session.id


def estimate_cost(usage: Any, pricing: dict[str, Any] | None) -> float | None:
    if not isinstance(usage, dict) or not isinstance(pricing, dict):
        return None
    per_token = pricing.get("per_1m_tokens")
    if not isinstance(per_token, dict):
        return 0.0 if pricing.get("billing_model") in {"local", "institutional"} else None
    input_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
    output_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
    if not isinstance(input_tokens, (int, float)) or not isinstance(output_tokens, (int, float)):
        return None
    input_price = per_token.get("input")
    output_price = per_token.get("output")
    if not isinstance(input_price, (int, float)) or not isinstance(output_price, (int, float)):
        return None
    return round(input_tokens * input_price / 1_000_000 + output_tokens * output_price / 1_000_000, 8)
