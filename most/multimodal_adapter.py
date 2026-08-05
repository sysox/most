"""ExecutionManager adapter for capability-specific AI operations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .adapters import Connectivity, Observability
from .http_transport import urllib_json_transport
from .multimodal import (
    analyze_image,
    analyze_image_openai_compatible,
    embed,
    embed_openai_compatible,
    generate_image,
    synthesize_speech,
    transcribe_audio,
)


@dataclass(frozen=True, slots=True)
class MultimodalResult:
    value: Any
    journal_payload: dict[str, Any]


class MultimodalAdapter:
    adapter_type = "multimodal"
    _GEMINI_ONLY_OPERATIONS = frozenset({"image-generation", "speech-synthesis"})

    def validate_configuration(self, configuration: dict[str, Any]) -> list[str]:
        options = configuration.get("adapter_options", {})
        return [field for field in ("endpoint", "operation", "provider_id") if not options.get(field)]

    def resolve_connectivity(self, configuration: dict[str, Any]) -> Connectivity:
        options = configuration.get("adapter_options", {})
        endpoint = str(options.get("endpoint", ""))
        host = urlparse(endpoint).hostname or "unknown"
        provider = str(options.get("provider_id", ""))
        if host in {"localhost", "127.0.0.1", "::1"}:
            return Connectivity(endpoint, "local", "localhost", "DECLARED", (f"provider host: {host}",))
        return Connectivity(endpoint, "provider-cloud", "public-internet", "DECLARED", (f"provider: {provider}", f"provider host: {host}"))

    def get_observability_profile(self, configuration: dict[str, Any]) -> Observability:
        return Observability.STRUCTURED_STREAM

    def execute(self, request: dict[str, Any], configuration: dict[str, Any], credential: str | None = None) -> MultimodalResult:
        options = configuration["adapter_options"]
        endpoint = str(options["endpoint"])
        model = str(configuration["model_reference"])
        provider = str(options["provider_id"])
        operation = str(options["operation"])
        input_path = Path(str(options["input_path"])) if options.get("input_path") else None
        prompt = str(options.get("prompt", ""))

        if provider != "google" and operation in self._GEMINI_ONLY_OPERATIONS:
            raise ValueError(
                f"{operation} is currently supported only by the Google Gemini route; "
                f"provider {provider!r} has no verified compatible API"
            )

        if operation == "embedding":
            if input_path is None:
                raise ValueError("embedding input file is required")
            text = input_path.read_text(encoding="utf-8")
            if provider == "google":
                value = embed(urllib_json_transport, endpoint, model, credential or "", text)
                usage = {}
            else:
                value, usage = embed_openai_compatible(urllib_json_transport, endpoint, model, credential, text)
            return MultimodalResult(value, {"operation": operation, "dimensions": len(value), "usage": usage})
        if operation == "image-generation":
            value, mime = generate_image(urllib_json_transport, endpoint, model, credential or "", prompt)
            return MultimodalResult(value, {"operation": operation, "mime_type": mime, "bytes": len(value)})
        if operation == "speech-synthesis":
            value, mime = synthesize_speech(urllib_json_transport, endpoint, model, credential or "", prompt)
            return MultimodalResult(value, {"operation": operation, "mime_type": mime, "bytes": len(value)})
        if operation == "image-analysis":
            if input_path is None:
                raise ValueError("image input is required")
            if provider == "google":
                value = analyze_image(urllib_json_transport, endpoint, model, credential or "", input_path, prompt)
                usage = {}
            else:
                value, usage = analyze_image_openai_compatible(urllib_json_transport, endpoint, model, credential, input_path, prompt)
            return MultimodalResult(value, {"operation": operation, "usage": usage})
        if operation == "transcription":
            if input_path is None:
                raise ValueError("audio input is required")
            value = transcribe_audio(endpoint, model, credential, input_path)
            return MultimodalResult(value, {"operation": operation})
        raise ValueError(f"unsupported multimodal operation: {operation}")
