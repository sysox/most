"""Unified model and access-route selection."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import yaml

ENVIRONMENT_KEYS = {
    "openai": "OPENAI_API_KEY",
    "einfra": "CERIT_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
}

CLI_EXECUTABLES = {"openai": "codex", "anthropic": "claude", "google": "agy"}


def load_model_options(catalog_path: Path = Path("ai-catalog.yaml"), discovered_path: Path = Path("ai-discovered.yaml")) -> list[dict[str, Any]]:
    catalog = _load(catalog_path)
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


def select_model(options: list[dict[str, Any]], provider_id: str | None, model_id: str, route: str = "auto") -> dict[str, Any]:
    matches = [option for option in options if option["model_id"] == model_id and (provider_id is None or option["provider_id"] == provider_id)]
    if not matches:
        raise ValueError(f"model not found in catalog: {provider_id + '/' if provider_id else ''}{model_id}")
    if route != "auto":
        matches = [option for option in matches if option["access_method"] == route]
        if not matches:
            raise ValueError(f"route {route!r} is not configured for {model_id}")
    ranked = sorted(matches, key=_route_rank)
    selected = dict(ranked[0])
    if selected["access_method"] == "api" and selected["provider_id"] != "openai":
        raise ValueError(f"native API route is not implemented for {selected['provider_id']}")
    if selected["access_method"] == "api" and selected["provider_id"] == "openai":
        selected["adapter_type"] = "openai-api"
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
        "status": model.get("status", "unknown"),
        "access_method": method_id,
        "adapter_type": "",
        "endpoint": method.get("endpoint"),
        "executable": executable,
        "credential_env": credential_env,
        "credential_available": bool(os.environ.get(credential_env, "")) if credential_env else False,
        "executable_available": bool(executable and shutil.which(str(executable))),
        "pricing": model.get("pricing", provider.get("pricing", {})),
    }


def _route_rank(option: dict[str, Any]) -> tuple[int, int]:
    method = option["access_method"]
    if method == "openai-compatible":
        return (0, 0)
    if method == "api" and option["provider_id"] == "openai" and option["credential_available"]:
        return (1, 0)
    if method == "cli" and option["executable_available"]:
        return (2, 0)
    return (9, 0)


def _load(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}
