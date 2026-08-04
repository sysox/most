import base64
from pathlib import Path

from most.multimodal import (
    analyze_image,
    analyze_image_openai_compatible,
    embed,
    embed_openai_compatible,
    generate_image,
    synthesize_speech,
    transcribe_audio,
)
from most.openai_compatible import HTTPResponse


def test_embedding_decodes_vector():
    vector = embed(lambda url, headers, payload: HTTPResponse(200, {"embedding": {"values": [1, 2.5]}}), "https://example/v1beta", "models/embed", "secret", "hello")
    assert vector == [1.0, 2.5]


def test_image_and_audio_outputs_decode_inline_data():
    encoded = base64.b64encode(b"data").decode()

    def transport(url, headers, payload):
        mime = "image/png" if "IMAGE" in payload.get("generationConfig", {}).get("responseModalities", []) else "audio/wav"
        return HTTPResponse(200, {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": mime, "data": encoded}}]}}]})

    image, image_mime = generate_image(transport, "https://example/v1beta", "image-model", "secret", "draw")
    audio, audio_mime = synthesize_speech(transport, "https://example/v1beta", "speech-model", "secret", "say")
    assert (image, image_mime) == (b"data", "image/png")
    assert (audio, audio_mime) == (b"data", "audio/wav")


def test_image_analysis_sends_file_as_inline_data(tmp_path: Path):
    image_path = tmp_path / "image.png"
    image_path.write_bytes(b"png")
    calls = []

    def transport(url, headers, payload):
        calls.append(payload)
        return HTTPResponse(200, {"candidates": [{"content": {"parts": [{"text": "answer"}]}}]})

    assert analyze_image(transport, "https://example/v1beta", "vision-model", "secret", image_path, "describe") == "answer"
    part = calls[0]["contents"][0]["parts"][1]["inlineData"]
    assert part["mimeType"] == "image/png"
    assert part["data"] == base64.b64encode(b"png").decode()


def test_transcription_posts_audio_as_multipart(tmp_path: Path, monkeypatch):
    audio_path = tmp_path / "recording.wav"
    audio_path.write_bytes(b"wav")
    captured = {}

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"text":"transcribed"}'

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("most.multimodal.urlopen", fake_urlopen)
    assert transcribe_audio("https://api.openai.com/v1", "whisper-1", "secret", audio_path) == "transcribed"
    assert captured["request"].full_url.endswith("/audio/transcriptions")
    assert b"whisper-1" in captured["request"].data
    assert b"wav" in captured["request"].data
    assert captured["request"].headers["Authorization"] == "Bearer secret"


def test_openai_compatible_embedding_and_image_analysis():
    def transport(url, headers, payload):
        if url.endswith("/embeddings"):
            return HTTPResponse(200, {"data": [{"embedding": [0.1, 0.2]}], "usage": {"prompt_tokens": 2}})
        return HTTPResponse(200, {"choices": [{"message": {"content": "looks good"}}], "usage": {"prompt_tokens": 3, "completion_tokens": 2}})

    vector, embedding_usage = embed_openai_compatible(transport, "http://localhost/v1", "embedding", None, "hello")
    assert vector == [0.1, 0.2]
    assert embedding_usage["prompt_tokens"] == 2
    image_path = Path("/tmp/most-test-image.png")
    image_path.write_bytes(b"png")
    try:
        result, image_usage = analyze_image_openai_compatible(transport, "http://localhost/v1", "vision", None, image_path, "describe")
    finally:
        image_path.unlink(missing_ok=True)
    assert result == "looks good"
    assert image_usage["completion_tokens"] == 2
