"""Explicit policy resolution and exposure checks."""

from __future__ import annotations

from dataclasses import dataclass

from .models import ExposureAction, OverflowPolicy


@dataclass(frozen=True, slots=True)
class ExposureResolution:
    action: ExposureAction
    reason: str


def resolve_overflow_policy(request_override: OverflowPolicy | None, configuration: OverflowPolicy | None,
                            application_default: OverflowPolicy | None = None) -> OverflowPolicy:
    return request_override or configuration or application_default or OverflowPolicy.FAIL


def evaluate_exposure(declared_location: str, declared_network: str | None,
                      resolved_location: str, resolved_network: str | None,
                      allowed: bool = False, confirmation: bool = False) -> ExposureResolution:
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
        return ExposureResolution(ExposureAction.REQUIRE_CONFIRMATION, "exposure-increasing transition requires approval")
    return ExposureResolution(ExposureAction.FAIL, "exposure-increasing transition is not allowed")
