"""Capability-specific Google Gemini API operations."""

from __future__ import annotations

import base64
import mimetypes
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .openai_compatible import HTTPResponse

Transport = Callable[[str, dict[str, str], dict[str, Any]], HTTPResponse]


def embed(transport: Transport, base_url: str, model: str, credential: str, text: str) -> list[float]:
    body = _generate(transport, base_url, model, credential, "embedContent", {"content": {"parts": [{"text": text}]}})
    values = body.get("embedding", {}).get("values")
    if not isinstance(values, list) or not all(isinstance(value, (int, float)) for value in values):
        raise RuntimeError("Gemini embedding response did not contain numeric values")
    return [float(value) for value in values]


def embed_openai_compatible(transport: Transport, base_url: str, model: str, credential: str | None, text: str) -> tuple[list[float], dict[str, Any]]:
    headers = {"content-type": "application/json"}
    if credential:
        headers["authorization"] = f"Bearer {credential}"
    response = transport(base_url.rstrip("/") + "/embeddings", headers, {"model": model, "input": text})
    if response.status >= 400:
        raise RuntimeError(f"embedding returned HTTP {response.status}: {response.body.get('error', response.body)}")
    data = response.body.get("data", [])
    values = data[0].get("embedding") if data and isinstance(data[0], dict) else None
    if not isinstance(values, list) or not all(isinstance(value, (int, float)) for value in values):
        raise RuntimeError("embedding response did not contain numeric values")
    return [float(value) for value in values], response.body.get("usage", {})


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


def analyze_image_openai_compatible(transport: Transport, base_url: str, model: str, credential: str | None, image_path: Path, prompt: str) -> tuple[str, dict[str, Any]]:
    import base64
    data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    mime = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
    content = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}},
    ]
    headers = {"content-type": "application/json"}
    if credential:
        headers["authorization"] = f"Bearer {credential}"
    response = transport(base_url.rstrip("/") + "/chat/completions", headers, {"model": model, "messages": [{"role": "user", "content": content}]})
    if response.status >= 400:
        raise RuntimeError(f"image analysis returned HTTP {response.status}: {response.body.get('error', response.body)}")
    choices = response.body.get("choices", [])
    text = choices[0].get("message", {}).get("content") if choices else None
    if not isinstance(text, str):
        raise TypeError("image analysis response did not contain text")
    return text, response.body.get("usage", {})


def transcribe_audio(base_url: str, model: str, credential: str | None, audio_path: Path) -> str:
    boundary = "most-" + uuid.uuid4().hex
    data = audio_path.read_bytes()
    filename = audio_path.name
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n{model}\r\n".encode(),
        (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
            f"Content-Type: {mime}\r\n\r\n"
        ).encode() + data + b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    headers = {"content-type": f"multipart/form-data; boundary={boundary}"}
    if credential:
        headers["authorization"] = f"Bearer {credential}"
    request = Request(base_url.rstrip("/") + "/audio/transcriptions", data=b"".join(parts), headers=headers, method="POST")
    try:
        with urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"transcription returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise ConnectionError(f"transcription connection failed: {exc.reason}") from exc
    import json
    parsed = json.loads(body)
    text = parsed.get("text") if isinstance(parsed, dict) else None
    if not isinstance(text, str):
        raise TypeError("transcription response did not contain text")
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
