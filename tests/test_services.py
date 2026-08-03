from pathlib import Path

from most.adapters import create_default_registry
from most.models import AIConfiguration
from most.network import NetworkInspector
from most.services import ConfigurationService, ConnectivityService


def test_configuration_service_round_trip(tmp_path: Path):
    service = ConfigurationService(tmp_path)
    configuration = AIConfiguration(name="local", provider_id="local", access_method_id="openai-compatible")
    service.save(configuration)
    assert service.get(configuration.id)["name"] == "local"


def test_connectivity_service_uses_conservative_inspection(tmp_path: Path):
    registry = create_default_registry()
    service = ConnectivityService(registry, NetworkInspector())
    resolution = service.resolve("openai-compatible", {"adapter_options": {"base_url": "http://localhost:11434/v1"}, "model_reference": "m"})
    assert resolution.location == "local"
