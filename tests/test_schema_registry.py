import pytest

from most.serialization import SchemaRegistry, UnsupportedSchemaError, versioned_payload


def test_schema_registry_dispatches_and_preserves_unknown_fields():
    registry = SchemaRegistry()
    registry.register("TEST", 1, lambda payload: payload)
    payload = versioned_payload({"unknown_extension": {"x": 1}}, record_type="TEST", record_id="id")
    assert registry.read(payload)["unknown_extension"] == {"x": 1}


def test_schema_registry_rejects_newer_versions_explicitly():
    registry = SchemaRegistry()
    with pytest.raises(UnsupportedSchemaError):
        registry.read(versioned_payload({}, record_type="TEST", record_id="id", schema_version=2))
