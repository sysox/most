"""Execution lifecycle validation and immutable transition events."""

from __future__ import annotations

from dataclasses import replace

from .models import Execution, ExecutionState, utc_now

VALID_TRANSITIONS: dict[ExecutionState, frozenset[ExecutionState]] = {
    ExecutionState.CREATED: frozenset({ExecutionState.VALIDATING}),
    ExecutionState.VALIDATING: frozenset({ExecutionState.READY, ExecutionState.WAITING_FOR_USER, ExecutionState.FAILED, ExecutionState.CANCELLED}),
    ExecutionState.READY: frozenset({ExecutionState.STARTING, ExecutionState.CANCELLED}),
    ExecutionState.STARTING: frozenset({ExecutionState.RUNNING, ExecutionState.WAITING_FOR_USER, ExecutionState.FAILED, ExecutionState.CANCELLED}),
    ExecutionState.RUNNING: frozenset({ExecutionState.STREAMING, ExecutionState.WAITING_FOR_USER, ExecutionState.COMPLETED, ExecutionState.FAILED, ExecutionState.CANCELLED}),
    ExecutionState.STREAMING: frozenset({ExecutionState.WAITING_FOR_USER, ExecutionState.COMPLETED, ExecutionState.FAILED, ExecutionState.CANCELLED}),
    ExecutionState.WAITING_FOR_USER: frozenset({ExecutionState.READY, ExecutionState.RUNNING, ExecutionState.STREAMING, ExecutionState.FAILED, ExecutionState.CANCELLED}),
    ExecutionState.COMPLETED: frozenset(),
    ExecutionState.FAILED: frozenset(),
    ExecutionState.CANCELLED: frozenset(),
}


def transition(execution: Execution, target: ExecutionState, *, reason: str | None = None) -> tuple[Execution, dict[str, object]]:
    if target not in VALID_TRANSITIONS[execution.state]:
        raise ValueError(f"invalid execution transition: {execution.state.value} -> {target.value}")
    updated = replace(execution, state=target, waiting_reason=reason, updated_at=utc_now())
    event = {
        "event_type": "STATUS",
        "execution_id": execution.id,
        "from_state": execution.state.value,
        "to_state": target.value,
        "waiting_reason": reason,
        "created_at": updated.updated_at,
    }
    return updated, event
