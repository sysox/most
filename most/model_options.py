"""Unified model and access-route selection."""

from __future__ import annotations

import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from .catalog_schema import validate_catalog
from .modalities import model_modalities

ENVIRONMENT_KEYS = {
    "openai": "OPENAI_API_KEY",
    "einfra": "CERIT_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
}

CLI_EXECUTABLES = {"openai": "codex", "anthropic": "claude", "google": "agy"}


def load_model_options(catalog_path: Path = Path("ai-catalog.yaml"), discovered_path: Path = Path("ai-discovered.yaml")) -> list[dict[str, Any]]:
    catalog = validate_catalog(_load(catalog_path))
    discovered = _load(discovered_path) if discovered_path.exists() else {}
    discovered_by_provider = {
        str(provider.get("id")): provider
        for provider in discovered.get("providers", [])
        if isinstance(provider, dict)
    }
    options: list[dict[str, Any]] = []
    for provider in catalog.get("providers", []):
        if not isinstance(provider, dict):
            continue
        provider_id = str(provider.get("id"))
        models = {str(model.get("id")): dict(model) for model in provider.get("models", []) if isinstance(model, dict) and model.get("id")}
        for model in discovered_by_provider.get(provider_id, {}).get("models", []):
            if isinstance(model, dict) and model.get("id"):
                models.setdefault(str(model["id"]), dict(model))
        for model_id, model in models.items():
            for method in provider.get("access_methods", []):
                if isinstance(method, dict):
                    options.append(_option(provider, method, model_id, model))
    return options


def refresh_if_stale(catalog_path: Path, discovered_path: Path, *, max_age_hours: float = 24.0) -> bool:
    """Refresh dynamic discovery when stale, preserving the last good snapshot."""
    if discovered_path.exists():
        age_seconds = datetime.now(UTC).timestamp() - discovered_path.stat().st_mtime
        if age_seconds < max_age_hours * 3600:
            return False
    from .catalog_audit import audit_catalog

    discovered_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=discovered_path.parent, prefix=".ai-discovered-", suffix=".yaml", delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        results, _ = audit_catalog(catalog_path, discovered_path=temporary_path)
        has_models = any(result.model_id and "exact model discovered" in result.reason for result in results)
        if has_models:
            temporary_path.replace(discovered_path)
            return True
        return False
    finally:
        temporary_path.unlink(missing_ok=True)


def select_model(
    options: list[dict[str, Any]], provider_id: str | None, model_id: str, route: str = "auto",
    required_capability: str | None = None, required_input_modality: str | None = None,
    required_output_modality: str | None = None,
) -> dict[str, Any]:
    matches = [option for option in options if option["model_id"] == model_id and (provider_id is None or option["provider_id"] == provider_id)]
    if not matches:
        raise ValueError(f"model not found in catalog: {provider_id + '/' if provider_id else ''}{model_id}")
    if required_capability and not any(required_capability in option.get("capabilities", []) for option in matches):
        available = sorted({capability for option in matches for capability in option.get("capabilities", [])})
        raise ValueError(f"model {model_id!r} does not support {required_capability}; capabilities: {', '.join(available) or 'unknown'}")
    if required_input_modality and not any(required_input_modality in option.get("input_modalities", []) for option in matches):
        raise ValueError(f"model {model_id!r} does not accept {required_input_modality} input")
    if required_output_modality and not any(required_output_modality in option.get("output_modalities", []) for option in matches):
        raise ValueError(f"model {model_id!r} does not produce {required_output_modality} output")
    if route != "auto":
        matches = [option for option in matches if option["access_method"] == route]
        if not matches:
            raise ValueError(f"route {route!r} is not configured for {model_id}")
    ranked = sorted(matches, key=_route_rank)
    selected = dict(ranked[0])
    if selected["access_method"] == "api" and selected["provider_id"] == "openai":
        selected["adapter_type"] = "openai-api"
    elif selected["access_method"] == "api" and selected["provider_id"] == "anthropic":
        selected["adapter_type"] = "anthropic-api"
    elif selected["access_method"] == "api" and selected["provider_id"] == "google":
        selected["adapter_type"] = "gemini-api"
    elif selected["access_method"] in {"api", "openai-compatible"}:
        selected["adapter_type"] = "openai-compatible"
    elif selected["access_method"] == "cli":
        selected["adapter_type"] = "provider-cli"
    else:
        raise ValueError(f"unsupported access method: {selected['access_method']}")
    return selected


def _option(provider: dict[str, Any], method: dict[str, Any], model_id: str, model: dict[str, Any]) -> dict[str, Any]:
    provider_id = str(provider["id"])
    method_id = str(method["id"])
    credential_env = ENVIRONMENT_KEYS.get(provider_id)
    executable = method.get("executable") or CLI_EXECUTABLES.get(provider_id)
    return {
        "provider_id": provider_id,
        "provider_name": provider.get("name", provider_id),
        "model_id": model_id,
        "model_kind": model.get("kind", "curated"),
        "capabilities": model.get("capabilities", []),
        "input_modalities": model_modalities(provider_id, model_id, model)[0],
        "output_modalities": model_modalities(provider_id, model_id, model)[1],
        "status": model.get("status", "unknown"),
        "access_method": method_id,
        "adapter_type": "",
        "endpoint": method.get("endpoint"),
        "executable": executable,
        "credential_env": credential_env,
        "credential_available": _credential_available(provider_id, credential_env),
        "executable_available": bool(executable and shutil.which(str(executable))),
        "pricing": model.get("pricing", provider.get("pricing", {})),
    }


def _route_rank(option: dict[str, Any]) -> tuple[int, int]:
    method = option["access_method"]
    if method == "openai-compatible":
        # A configured compatible endpoint is preferred only when its required
        # credential is available.  Local endpoints normally have no credential
        # requirement and remain eligible.
        requires_credential = bool(option.get("credential_env")) and option.get("provider_id") not in {"ollama"}
        if option.get("endpoint") and (not requires_credential or option.get("credential_available")):
            return (0, 0)
        return (9, 0)
    if method == "api" and option["credential_available"]:
        return (1, 0)
    if method == "cli" and option["executable_available"]:
        return (2, 0)
    return (9, 0)


def _credential_available(provider_id: str, environment_name: str | None) -> bool:
    from .credentials import resolve_provider_credential
    return resolve_provider_credential(provider_id, environment_name) is not None


def _load(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}
