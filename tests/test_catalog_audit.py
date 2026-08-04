from pathlib import Path

from most.catalog_audit import (
    _model_ids,
    _model_type,
    _sync_discovered_models,
    audit_catalog,
)


def test_model_ids_support_nested_discovery_responses():
    assert _model_ids({"data": {"models": [{"name": "mini"}, {"id": "coder"}]}}) == {"mini", "coder"}
    assert _model_ids({"data": [{"id": "uuid", "name": "kimi-k2"}]}) == {"kimi-k2"}
    assert _model_ids({"data": [{"id": "6ff8b176-d74b-46e6-9d2a-f9185414d721"}]}) == set()


def test_model_types_group_specialized_models():
    assert _model_type("qwen3-embedding-4b") == "embedding"
    assert _model_type("qwen3-reranker-4b") == "reranker"
    assert _model_type("whisper-large-v3") == "speech"
    assert _model_type("qwen3.5-122b") == "chat/reason"


def test_sync_discovered_models_adds_capability_metadata():
    catalog = {"providers": [{"id": "einfra", "models": []}]}
    from most.catalog_audit import AuditResult
    _sync_discovered_models(catalog, [AuditResult("einfra", "api", "qwen3.5", "available", "exact model discovered")])
    assert catalog["providers"][0]["models"] == [{
        "id": "qwen3.5", "status": "available", "kind": "discovered", "capabilities": ["chat"],
        "input_modalities": ["text"], "output_modalities": ["text"]
    }]


def test_audit_updates_only_confirmed_model_statuses(tmp_path: Path, monkeypatch):
    catalog_path = tmp_path / "catalog.yaml"
    catalog_path.write_text("""
providers:
  - id: openai
    access_methods:
      - id: api
        model_discovery:
          method: GET
          endpoint: https://api.openai.com/v1/models
    models:
      - id: gpt-present
        status: unknown
        capabilities: [chat]
      - id: gpt-missing
        status: available
        capabilities: [chat]
""", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "secret")

    def fetch(url, headers):
        assert headers["authorization"] == "Bearer secret"
        return 200, {"data": [{"id": "gpt-present"}]}

    results, _ = audit_catalog(catalog_path, update=True, fetch=fetch, executable_exists=lambda _: False)
    assert [(item.model_id, item.status) for item in results if item.model_id] == [
        ("gpt-present", "available"), ("gpt-missing", "unavailable")
    ]
    written = catalog_path.read_text(encoding="utf-8")
    assert "last_audited:" in written
    assert "status: unavailable" in written


def test_audit_reports_missing_cli_without_marking_models(tmp_path: Path):
    catalog_path = tmp_path / "catalog.yaml"
    catalog_path.write_text("""
providers:
  - id: openai
    access_methods:
      - id: cli
        executable: codex
    models: []
""", encoding="utf-8")
    results, _ = audit_catalog(catalog_path, executable_exists=lambda _: False)
    assert results[0].status == "unavailable"
    assert "not found" in results[0].reason
