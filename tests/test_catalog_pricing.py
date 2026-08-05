from datetime import UTC, datetime
from pathlib import Path

import pytest

from most.catalog_pricing import apply_pricing_updates


def test_pricing_update_requires_source_and_updates_model(tmp_path: Path):
    catalog = tmp_path / "catalog.yaml"
    updates = tmp_path / "prices.yaml"
    catalog.write_text("""
providers:
  - id: openai
    access_methods:
      - id: api
        endpoint: https://api.openai.com/v1
    models:
      - id: gpt-test
        status: available
        capabilities: [chat]
""", encoding="utf-8")
    updates.write_text("""
prices:
  - provider_id: openai
    model_id: gpt-test
    per_1m_tokens: {input: 1.0, output: 2.0, cached_input: 0.1}
    source:
      url: https://example.com/pricing
      checked_at: 2026-08-04
""", encoding="utf-8")
    apply_pricing_updates(catalog, updates, update=True)
    assert f"pricing_last_updated: '{datetime.now(UTC).date().isoformat()}'" in catalog.read_text(encoding="utf-8")


def test_pricing_update_rejects_http_sources(tmp_path: Path):
    catalog = tmp_path / "catalog.yaml"
    updates = tmp_path / "prices.yaml"
    catalog.write_text("providers: []\n", encoding="utf-8")
    updates.write_text("""
prices:
  - provider_id: x
    model_id: y
    per_1m_tokens: {input: 1, output: 2}
    source: {url: http://example.com, checked_at: 2026-08-04}
""", encoding="utf-8")
    with pytest.raises(ValueError, match="HTTPS"):
        apply_pricing_updates(catalog, updates)
