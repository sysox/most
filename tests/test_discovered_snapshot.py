from pathlib import Path

import yaml

from most.catalog_audit import AuditResult, _write_discovered_snapshot


def test_discovered_snapshot_keeps_dynamic_models_separate(tmp_path: Path):
    path = tmp_path / "ai-discovered.yaml"
    _write_discovered_snapshot(path, [AuditResult("einfra", "openai-compatible", "kimi-k3", "available", "exact model discovered")])
    snapshot = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert snapshot["providers"][0]["models"][0]["kind"] == "discovered"
    assert snapshot["providers"][0]["models"][0]["id"] == "kimi-k3"
    assert "reasoning" in snapshot["providers"][0]["models"][0]["suitability"]["tasks"]
