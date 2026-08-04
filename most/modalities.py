"""Model input/output modality metadata and conservative inference."""

from __future__ import annotations

from typing import Any


def infer_modalities(provider_id: str, model_id: str, capabilities: list[str] | tuple[str, ...] | None = None) -> tuple[list[str], list[str]]:
    name = model_id.lower()
    caps = set(capabilities or ())
    if "embedding" in caps or "embed" in name:
        return ["text"], ["embedding"]
    if "reranking" in caps or "rerank" in name:
        return ["text"], ["ranking"]
    if any(marker in name for marker in ("tts", "text-to-speech")):
        return ["text"], ["audio"]
    if "transcription" in caps or "speech-to-text" in caps or any(marker in name for marker in ("whisper", "transcri", "stt")):
        return ["audio"], ["text"]
    if "image" in caps or "image" in name:
        return ["text"], ["image"]
    if "chat" in caps or not caps:
        inputs = ["text"]
        if provider_id in {"google", "anthropic", "openai"}:
            inputs.append("image")
        return inputs, ["text"]
    return ["text"], ["text"]


def model_modalities(provider_id: str, model_id: str, model: dict[str, Any]) -> tuple[list[str], list[str]]:
    inferred_input, inferred_output = infer_modalities(provider_id, model_id, model.get("capabilities"))
    inputs = model.get("input_modalities")
    outputs = model.get("output_modalities")
    return (
        [str(value) for value in inputs] if isinstance(inputs, list) and inputs else inferred_input,
        [str(value) for value in outputs] if isinstance(outputs, list) and outputs else inferred_output,
    )
