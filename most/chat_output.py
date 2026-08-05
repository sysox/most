"""Structured output for machine-consumed chat stages."""

from __future__ import annotations

import json
from argparse import Namespace


def print_chat_result(args: Namespace, content: str, session_id: str, usage: dict | None = None) -> None:
    """Print one chat result using either the human or stage JSON contract."""
    if getattr(args, "json", False):
        payload = {
            "content": content,
            "session_id": session_id,
            "profile": getattr(args, "profile", None),
            "pipeline_id": getattr(args, "pipeline_id", None),
            "stage_index": getattr(args, "stage_index", None),
            "operation_id": getattr(args, "operation_id", None),
        }
        if usage:
            payload["usage"] = usage
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"assistant> {content}")


def print_chat_session(args: Namespace, session_id: str) -> None:
    if not getattr(args, "json", False):
        print(f"session: {session_id}")
