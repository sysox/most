"""Deterministic result-lineage and context selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import IntermediateResult


@dataclass(frozen=True, slots=True)
class ContextAssembly:
    lineage_result_ids: tuple[str, ...]
    excluded_result_ids: tuple[str, ...]
    transformations: tuple[str, ...]
    estimated_tokens: int = 0
    token_limit: int | None = None


class ContextOverflowError(ValueError):
    pass


def resolve_lineage(active_result_id: str, results: dict[str, IntermediateResult]) -> list[IntermediateResult]:
    lineage: list[IntermediateResult] = []
    current: str | None = active_result_id
    seen: set[str] = set()
    while current is not None:
        if current in seen:
            raise ValueError("result parent cycle detected")
        seen.add(current)
        result = results.get(current)
        if result is None:
            raise KeyError(f"unknown result {current}")
        lineage.append(result)
        current = result.parent_result_id
    lineage.reverse()
    return lineage


def assemble_context(active_result_id: str, results: dict[str, IntermediateResult]) -> ContextAssembly:
    lineage = resolve_lineage(active_result_id, results)
    lineage_ids = tuple(result.id for result in lineage)
    excluded = tuple(result.id for result in results.values() if result.id not in lineage_ids)
    return ContextAssembly(lineage_ids, excluded, ("root-to-active-result lineage",))


def estimate_tokens(messages: list[dict[str, Any]], source_items: list[str] | None = None) -> int:
    """Conservative fallback estimator: four characters are one token."""
    text = "\n".join(str(message.get("content", "")) for message in messages)
    text += "\n" + "\n".join(source_items or [])
    return max(0, (len(text) + 3) // 4)


def enforce_budget(messages: list[dict[str, Any]], *, token_limit: int,
                   reserved_output_tokens: int = 0, pinned_indices: set[int] | None = None) -> list[dict[str, Any]]:
    pinned = pinned_indices or set()
    working = list(enumerate(messages))
    if estimate_tokens([message for _, message in working]) + reserved_output_tokens <= token_limit:
        return [message for _, message in working]
    while working and estimate_tokens([message for _, message in working]) + reserved_output_tokens > token_limit:
        removable = next((position for position, (original, _) in enumerate(working) if original not in pinned), None)
        if removable is None:
            break
        working.pop(removable)
    if estimate_tokens([message for _, message in working]) + reserved_output_tokens > token_limit:
        raise ContextOverflowError("context exceeds token limit; explicit selection or confirmation is required")
    return [message for _, message in working]
