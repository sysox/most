import pytest

from most.models import AIConfiguration
from most.schemas import require_valid_ai_configuration, validate_ai_configuration


def test_configuration_schema_rejects_missing_identity():
    errors = validate_ai_configuration({"location": "local"})
    assert "provider_id is required" in errors


def test_configuration_service_schema_accepts_complete_record():
    configuration = AIConfiguration(name="Local", provider_id="local", access_method_id="openai-compatible")
    require_valid_ai_configuration({"id": configuration.id, "name": configuration.name, "provider_id": configuration.provider_id, "access_method_id": configuration.access_method_id, "location": configuration.location, "context_overflow_policy": configuration.context_overflow_policy, "adapter_options": {}})


def test_configuration_schema_rejects_unknown_location():
    with pytest.raises(ValueError):
        require_valid_ai_configuration({"id": "i", "name": "n", "provider_id": "p", "access_method_id": "a", "location": "unsafe"})
