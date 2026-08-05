import pytest

from most.models import OverflowPolicy
from most.policies import (
    PolicyOverrides,
    enforce_route_sensitivity,
    resolve_policies,
    route_policy_decision,
)


def test_policy_precedence_records_sources():
    result = resolve_policies(
        {"context_overflow_policy": "TRIM_OLDEST"},
        {"context_overflow_policy": "SELECT_MANUALLY", "exposure_policy_reference": "app"},
        {"workspace_context_strategy": "HYBRID"},
        PolicyOverrides(context_overflow_policy=OverflowPolicy.FAIL, workspace_context_strategy="GIT_DIFF_ONLY"),
    )
    assert result.overflow_policy is OverflowPolicy.FAIL
    assert result.workspace_context_strategy == "GIT_DIFF_ONLY"
    assert result.exposure_policy_reference == "app"
    assert result.sources["overflow"] == "request_override"


def test_less_restrictive_exposure_override_requires_explicit_permission():
    with pytest.raises(PermissionError):
        resolve_policies({}, overrides=PolicyOverrides(exposure_policy_reference="allow-public"))


def test_browser_route_is_blocked_for_sensitive_workloads():
    with pytest.raises(PermissionError, match="browser-chat is not allowed"):
        enforce_route_sensitivity("browser", "sensitive")


def test_non_browser_routes_can_carry_sensitive_workloads():
    enforce_route_sensitivity("official-cloud-api", "sensitive")


def test_standalone_route_policy_decision_matches_execution_enforcement():
    decision = route_policy_decision("browser", "sensitive")
    assert decision.allowed is False
    assert decision.reason == "browser-chat is not allowed for sensitive workloads"
    with pytest.raises(PermissionError, match=decision.reason):
        enforce_route_sensitivity("browser", "sensitive")


def test_model_policy_check_does_not_require_credentials(tmp_path):
    from most.policies import model_policy_reason

    catalog = tmp_path / "catalog.yaml"
    catalog.write_text("""
providers:
  - id: einfra
    models:
      - id: safe
        is_external_passthrough: false
      - id: unknown
        is_external_passthrough: true
""", encoding="utf-8")
    assert model_policy_reason("einfra", "safe", "sensitive", catalog) is None
    assert "not eligible" in model_policy_reason("einfra", "unknown", "sensitive", catalog)
