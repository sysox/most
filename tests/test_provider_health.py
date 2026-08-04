from pathlib import Path

from most.catalog_audit import AuditResult
from most.provider_health import format_health, record_failure


def test_failure_check_reports_replacement_candidates(monkeypatch, tmp_path: Path):
    def fake_audit(*args, **kwargs):
        return [
            AuditResult("einfra", "openai-compatible", "old-model", "unavailable", "model not returned by provider"),
            AuditResult("einfra", "openai-compatible", "qwen3.5-122b", "available", "exact model discovered"),
        ], {}

    monkeypatch.setattr("most.provider_health.audit_catalog", fake_audit)
    record = record_failure(
        tmp_path, tmp_path / "catalog.yaml", tmp_path / "discovered.yaml",
        provider_id="einfra", model_id="old-model", route="openai-compatible", error="HTTP 404",
    )
    assert record["verification"] == "unavailable"
    assert record["replacement_candidates"] == ["qwen3.5-122b"]
    assert "replacements: qwen3.5-122b" in format_health([record])
