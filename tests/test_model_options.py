import os
from pathlib import Path

from most.model_options import load_model_options, refresh_if_stale, select_model


def test_select_model_prefers_openai_api_when_key_is_available(tmp_path: Path, monkeypatch):
    catalog = tmp_path / "catalog.yaml"
    discovered = tmp_path / "discovered.yaml"
    catalog.write_text("""
providers:
  - id: openai
    name: OpenAI
    access_methods:
      - id: cli
        executable: codex
      - id: api
        endpoint: https://api.openai.com/v1
    models:
      - id: gpt-test
        status: available
        capabilities: [chat]
""", encoding="utf-8")
    discovered.write_text("providers: []\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    selected = select_model(load_model_options(catalog, discovered), "openai", "gpt-test")
    assert selected["access_method"] == "api"
    assert selected["adapter_type"] == "openai-api"


def test_discovered_models_are_available_to_unified_options(tmp_path: Path):
    catalog = tmp_path / "catalog.yaml"
    discovered = tmp_path / "discovered.yaml"
    catalog.write_text("providers:\n  - id: einfra\n    access_methods:\n      - id: openai-compatible\n        endpoint: https://llm.ai.e-infra.cz/v1\n    models: []\n", encoding="utf-8")
    discovered.write_text("providers:\n  - id: einfra\n    models:\n      - id: kimi-k3\n        status: available\n", encoding="utf-8")
    options = load_model_options(catalog, discovered)
    assert any(option["model_id"] == "kimi-k3" for option in options)


def test_select_model_rejects_non_chat_capability():
    options = [{"provider_id": "google", "model_id": "gemini-embedding-001", "capabilities": ["embedding"], "access_method": "api"}]
    try:
        select_model(options, "google", "gemini-embedding-001", required_capability="chat")
    except ValueError as exc:
        assert "does not support chat" in str(exc)
    else:
        raise AssertionError("embedding model was incorrectly accepted for chat")


def test_select_model_rejects_missing_input_modality():
    options = [{
        "provider_id": "ollama", "model_id": "text-model", "capabilities": ["chat"],
        "input_modalities": ["text"], "output_modalities": ["text"], "access_method": "openai-compatible",
    }]
    try:
        select_model(options, "ollama", "text-model", required_input_modality="image")
    except ValueError as exc:
        assert "does not accept image input" in str(exc)
    else:
        raise AssertionError("text-only model was incorrectly accepted for image input")


def test_refresh_if_stale_preserves_existing_snapshot_when_discovery_has_no_models(tmp_path: Path, monkeypatch):
    catalog = tmp_path / "catalog.yaml"
    discovered = tmp_path / "discovered.yaml"
    catalog.write_text("providers: []\n", encoding="utf-8")
    discovered.write_text("providers:\n  - id: old\n", encoding="utf-8")
    os.utime(discovered, (1, 1))
    assert refresh_if_stale(catalog, discovered) is False
    assert "old" in discovered.read_text(encoding="utf-8")
