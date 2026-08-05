from datetime import date
from pathlib import Path

import pytest
import yaml

CATALOG = Path(__file__).parents[1] / "ai-catalog.yaml"
STATUSES = {"available", "deprecated", "unavailable", "unknown"}
ACCESS_METHODS = {"openai-compatible", "cli", "api"}


def load_catalog():
    return yaml.safe_load(CATALOG.read_text(encoding="utf-8"))


def test_ai_catalog_has_provider_routes_and_pricing_metadata():
    catalog = load_catalog()

    assert catalog["catalog_version"] == 1
    providers_list = catalog["providers"]
    assert len({provider["id"] for provider in providers_list}) == len(providers_list)
    providers = {provider["id"]: provider for provider in providers_list}
    assert {"ollama", "einfra", "anthropic", "openai", "google"} <= providers.keys()

    for provider in providers.values():
        assert provider["kind"] in {"local", "einfra", "cloud"}
        assert provider["access_methods"]
        assert len({method["id"] for method in provider["access_methods"]}) == len(provider["access_methods"])
        for method in provider["access_methods"]:
            assert method["id"] in ACCESS_METHODS
            if method["id"] in {"openai-compatible", "api"}:
                assert method["endpoint"].startswith(("http://", "https://"))
            if method.get("model_discovery"):
                discovery = method["model_discovery"]
                assert discovery["method"] in {"GET", "CLI"}
                if discovery["method"] == "GET":
                    assert discovery["endpoint"].startswith(("http://", "https://"))
                else:
                    assert discovery["command"]
        assert "pricing" in provider
        assert "source" in provider["pricing"]
        assert provider["pricing"]["source"]["url"].startswith("https://")
        date.fromisoformat(str(provider["pricing"]["source"]["checked_at"]))
        pricing = provider["pricing"]
        if "user_cost" in pricing:
            assert isinstance(pricing["user_cost"], (int, float))
            assert pricing["user_cost"] >= 0
        per_token = pricing.get("per_1m_tokens")
        if per_token is not None:
            assert set(per_token) >= {"input", "output"}
            for value in per_token.values():
                assert value is None or (isinstance(value, (int, float)) and value >= 0)
        for model in provider["models"]:
            assert model["id"]
            assert model["status"] in STATUSES
            assert model["capabilities"]
            if model.get("kind") == "maintained-alias":
                assert model.get("resolves_to")
            if provider["id"] == "einfra":
                assert model["is_external_passthrough"] is False

        if not provider["models"]:
            assert any(method.get("model_discovery") for method in provider["access_methods"])


def test_einfra_catalog_uses_dynamic_model_discovery_and_zero_user_cost():
    catalog = load_catalog()
    provider = next(item for item in catalog["providers"] if item["id"] == "einfra")
    access_method = provider["access_methods"][0]

    assert access_method["model_discovery"]["endpoint"].endswith("/model/info")
    assert provider["pricing"]["user_cost"] == 0
    assert provider["pricing"]["per_1m_tokens"]["input"] is None


@pytest.mark.parametrize("provider_id", ["ollama", "einfra", "anthropic", "openai", "google"])
def test_every_catalog_provider_has_a_route(provider_id):
    catalog = load_catalog()
    provider = next(item for item in catalog["providers"] if item["id"] == provider_id)
    assert provider["access_methods"]


@pytest.mark.parametrize(
    "provider_id,model_id",
    [
        (provider["id"], model["id"])
        for provider in load_catalog()["providers"]
        for model in provider["models"]
    ],
)
def test_every_listed_model_has_status_and_capability(provider_id, model_id):
    catalog = load_catalog()
    provider = next(item for item in catalog["providers"] if item["id"] == provider_id)
    model = next(item for item in provider["models"] if item["id"] == model_id)
    assert model["status"] in STATUSES
    assert isinstance(model["capabilities"], list)
    assert model["capabilities"]
    assert isinstance(model["input_modalities"], list)
    assert model["input_modalities"]
    assert isinstance(model["output_modalities"], list)
    assert model["output_modalities"]
