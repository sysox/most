from most.cloud_adapter import CloudAPIAdapter
from most.openai_compatible import HTTPResponse


def test_cloud_adapter_requires_credential_and_never_falls_back():
    calls = []
    adapter = CloudAPIAdapter(lambda url, headers, payload: calls.append((url, headers, payload)) or HTTPResponse(200, {}))
    configuration = {"adapter_options": {"base_url": "https://provider.example/api", "api_key_header": "x-api-key"}}
    try:
        adapter.execute({}, configuration)
    except PermissionError:
        pass
    else:
        raise AssertionError("credential must be required")
    response = adapter.execute({}, configuration, "opaque")
    assert response.status == 200
    assert calls[0][1]["x-api-key"] == "opaque"
