from pathlib import Path

import yaml

CATALOG = Path(__file__).parents[1] / "ai-catalog.yaml"


def test_ai_catalog_has_provider_routes_and_pricing_metadata():
    catalog = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))

    assert catalog["catalog_version"] == 1
    providers = {provider["id"]: provider for provider in catalog["providers"]}
    assert {"ollama", "einfra", "anthropic", "openai", "google"} <= providers.keys()

    for provider in providers.values():
        assert provider["access_methods"]
        assert "pricing" in provider
        assert "source" in provider["pricing"]
        assert provider["pricing"]["source"]["url"].startswith("https://")
        for model in provider["models"]:
            assert model["id"]
            assert model["status"] in {"available", "deprecated", "unavailable", "unknown"}


def test_einfra_catalog_uses_dynamic_model_discovery_and_zero_user_cost():
    catalog = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    provider = next(item for item in catalog["providers"] if item["id"] == "einfra")
    access_method = provider["access_methods"][0]

    assert access_method["model_discovery"]["endpoint"].endswith("/model/info")
    assert provider["pricing"]["user_cost"] == 0
    assert provider["pricing"]["per_1m_tokens"]["input"] is None
