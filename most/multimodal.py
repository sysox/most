"""Capability-specific Google Gemini API operations."""

from __future__ import annotations

import base64
import mimetypes
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .openai_compatible import HTTPResponse

Transport = Callable[[str, dict[str, str], dict[str, Any]], HTTPResponse]


def embed(transport: Transport, base_url: str, model: str, credential: str, text: str) -> list[float]:
    body = _generate(transport, base_url, model, credential, "embedContent", {"content": {"parts": [{"text": text}]}})
    values = body.get("embedding", {}).get("values")
    if not isinstance(values, list) or not all(isinstance(value, (int, float)) for value in values):
        raise RuntimeError("Gemini embedding response did not contain numeric values")
    return [float(value) for value in values]


def generate_image(transport: Transport, base_url: str, model: str, credential: str, prompt: str) -> tuple[bytes, str]:
    body = _generate(
        transport, base_url, model, credential, "generateContent",
        {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}},
    )
    return _inline_data(body, "image")


def synthesize_speech(transport: Transport, base_url: str, model: str, credential: str, text: str) -> tuple[bytes, str]:
    body = _generate(
        transport, base_url, model, credential, "generateContent",
        {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"]},
        },
    )
    return _inline_data(body, "audio")


def analyze_image(transport: Transport, base_url: str, model: str, credential: str, image_path: Path, prompt: str) -> str:
    data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    mime = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
    body = _generate(
        transport, base_url, model, credential, "generateContent",
        {"contents": [{"parts": [{"text": prompt}, {"inlineData": {"mimeType": mime, "data": data}}]}]},
    )
    text = "".join(
        part["text"]
        for candidate in body.get("candidates", [])
        if isinstance(candidate, dict)
        for part in candidate.get("content", {}).get("parts", [])
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    )
    if not text:
        raise RuntimeError("Gemini image-analysis response did not contain text")
    return text


def _generate(transport: Transport, base_url: str, model: str, credential: str, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
    model_name = model.removeprefix("models/")
    suffix = f"/models/{model_name}:{operation}"
    response = transport(
        base_url.rstrip("/") + suffix,
        {"content-type": "application/json", "x-goog-api-key": credential},
        payload,
    )
    if response.status >= 400:
        raise RuntimeError(f"Google Gemini returned HTTP {response.status}: {response.body.get('error', response.body)}")
    return response.body


def _inline_data(body: dict[str, Any], modality: str) -> tuple[bytes, str]:
    for candidate in body.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        for part in candidate.get("content", {}).get("parts", []):
            inline = part.get("inlineData") if isinstance(part, dict) else None
            if isinstance(inline, dict) and isinstance(inline.get("data"), str):
                mime = str(inline.get("mimeType", "application/octet-stream"))
                if modality in mime or (modality == "audio" and mime.startswith("audio/")):
                    return base64.b64decode(inline["data"]), mime
    raise RuntimeError(f"Gemini response did not contain {modality} data")
