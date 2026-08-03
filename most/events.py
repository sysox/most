"""Tamper-evident execution stream event envelopes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .models import new_id, utc_now


@dataclass(frozen=True, slots=True)
class StreamEvent:
    event_id: str
    execution_id: str
    sequence_number: int
    event_type: str
    created_at: str
    observation_source: str
    payload: dict[str, Any]
    previous_event_hash: str | None
    event_hash: str


def create_stream_event(execution_id: str, sequence_number: int, event_type: str,
                        payload: dict[str, Any], observation_source: str = "PROVIDER_EVENT",
                        previous_event_hash: str | None = None) -> StreamEvent:
    event_id = new_id()
    created_at = utc_now()
    unsigned = {
        "event_id": event_id,
        "execution_id": execution_id,
        "sequence_number": sequence_number,
        "event_type": event_type,
        "created_at": created_at,
        "observation_source": observation_source,
        "payload": payload,
        "previous_event_hash": previous_event_hash,
    }
    digest = hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return StreamEvent(**unsigned, event_hash=digest)
