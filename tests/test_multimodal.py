import base64
from pathlib import Path

from most.multimodal import analyze_image, embed, generate_image, synthesize_speech
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
