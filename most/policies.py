"""Explicit policy resolution and exposure checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .models import ExposureAction, OverflowPolicy


@dataclass(frozen=True, slots=True)
class ExposureResolution:
    action: ExposureAction
    reason: str


@dataclass(frozen=True, slots=True)
class PolicyResolution:
    exposure_policy_reference: str | None
    overflow_policy: OverflowPolicy
    workspace_context_strategy: str
    sources: dict[str, str]


@dataclass(frozen=True, slots=True)
class PolicyOverrides:
    exposure_policy_reference: str | None = None
    context_overflow_policy: OverflowPolicy | None = None
    workspace_context_strategy: str | None = None
    explicit_exposure_override: bool = False


@dataclass(frozen=True, slots=True)
class RoutePolicyDecision:
    allowed: bool
    reason: str
    access_method_id: str
    sensitivity_tier: str | None


def route_policy_decision(access_method_id: str, sensitivity_tier: str | None) -> RoutePolicyDecision:
    """Return the preflight decision shared with execution-time enforcement."""
    if sensitivity_tier not in {None, "normal", "sensitive"}:
        raise ValueError(f"unsupported sensitivity tier: {sensitivity_tier}")
    if access_method_id == "browser" and sensitivity_tier == "sensitive":
        return RoutePolicyDecision(False, "browser-chat is not allowed for sensitive workloads", access_method_id, sensitivity_tier)
    return RoutePolicyDecision(True, "route is allowed for the requested sensitivity tier", access_method_id, sensitivity_tier)


def model_policy_reason(provider_id: str, model_id: str | None, sensitivity_tier: str | None,
                        catalog_path: Path = Path("ai-catalog.yaml")) -> str | None:
    """Return a model-policy denial without reading credentials or calling a provider."""
    if sensitivity_tier != "sensitive" or provider_id != "einfra" or model_id is None:
        return None
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    for provider in catalog.get("providers", []) if isinstance(catalog, dict) else []:
        if not isinstance(provider, dict) or provider.get("id") != provider_id:
            continue
        for model in provider.get("models", []):
            if isinstance(model, dict) and model.get("id") == model_id:
                if model.get("is_external_passthrough") is False:
                    return None
                return "e-INFRA model is not eligible for sensitive workloads; passthrough status must be explicitly false"
    return "e-INFRA model is not eligible for sensitive workloads; model is not explicitly verified in the catalog"


def enforce_route_sensitivity(access_method_id: str, sensitivity_tier: str | None) -> None:
    """Reject routes that cannot safely carry sensitive workload content."""
    decision = route_policy_decision(access_method_id, sensitivity_tier)
    if not decision.allowed:
        raise PermissionError(decision.reason)


def resolve_policies(configuration: dict[str, Any], application_defaults: dict[str, Any] | None = None,
                    workspace_defaults: dict[str, Any] | None = None,
                    overrides: PolicyOverrides | None = None) -> PolicyResolution:
    defaults = application_defaults or {}
    workspace = workspace_defaults or {}
    requested = overrides or PolicyOverrides()
    if requested.exposure_policy_reference is not None and not requested.explicit_exposure_override:
        raise PermissionError("less restrictive exposure override requires explicit permission")
    exposure = requested.exposure_policy_reference or configuration.get("exposure_transition_policy_reference") or defaults.get("exposure_policy_reference")
    overflow = requested.context_overflow_policy or configuration.get("context_overflow_policy") or defaults.get("context_overflow_policy") or OverflowPolicy.FAIL
    strategy = requested.workspace_context_strategy or configuration.get("workspace_context_strategy") or workspace.get("workspace_context_strategy") or "EXPLICIT_SELECTION"
    if isinstance(overflow, str):
        overflow = OverflowPolicy(overflow)
    return PolicyResolution(
        exposure,
        overflow,
        str(strategy),
        {
            "exposure": "execution_override" if requested.exposure_policy_reference else "configuration" if configuration.get("exposure_transition_policy_reference") else "application_default" if defaults.get("exposure_policy_reference") else "built_in_default",
            "overflow": "request_override" if requested.context_overflow_policy else "configuration" if configuration.get("context_overflow_policy") else "application_default" if defaults.get("context_overflow_policy") else "built_in_default",
            "workspace": "interaction_override" if requested.workspace_context_strategy else "configuration" if configuration.get("workspace_context_strategy") else "workspace_default" if workspace.get("workspace_context_strategy") else "built_in_default",
        },
    )


def resolve_overflow_policy(request_override: OverflowPolicy | None, configuration: OverflowPolicy | None,
                            application_default: OverflowPolicy | None = None) -> OverflowPolicy:
    return request_override or configuration or application_default or OverflowPolicy.FAIL


def evaluate_exposure(declared_location: str, declared_network: str | None,
                      resolved_location: str, resolved_network: str | None,
                      allowed: bool = False, confirmation: bool = False,
                      resolved_confidence: str | None = None) -> ExposureResolution:
    uncertain = resolved_confidence == "UNKNOWN" or resolved_location == "unknown" or resolved_network == "unknown"
    if uncertain:
        if allowed or confirmation:
            return ExposureResolution(ExposureAction.ALLOW_BY_POLICY, "unknown connectivity explicitly approved")
        return ExposureResolution(ExposureAction.FAIL, "unknown connectivity is unsafe by default")
    changed = (declared_location, declared_network) != (resolved_location, resolved_network)
    exposure_increased = changed and (
        declared_location in {"local", "remote-private"}
        and resolved_location in {"remote-public", "provider-cloud"}
        or declared_network in {"localhost", "local-network", "Tailscale", "VPN"}
        and resolved_network == "public-internet"
    )
    if not exposure_increased:
        return ExposureResolution(ExposureAction.ALLOW_BY_POLICY, "no exposure-increasing transition")
    if allowed:
        return ExposureResolution(ExposureAction.ALLOW_BY_POLICY, "explicit stored rule matched")
    if confirmation:
        return ExposureResolution(ExposureAction.ALLOW_BY_POLICY, "exposure-increasing transition explicitly approved")
    return ExposureResolution(ExposureAction.FAIL, "exposure-increasing transition is not allowed")
