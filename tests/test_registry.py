from most.adapters import create_default_registry


def test_default_registry_contains_mvp_adapter_types():
    registry = create_default_registry()
    assert set(registry.types()) == {"browser", "cli", "official-cloud-api", "openai-api", "openai-compatible"}
