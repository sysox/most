"""Configuration-driven provider and model availability audit."""

from __future__ import annotations

import os
import re
import shutil
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml


@dataclass(frozen=True, slots=True)
class AuditResult:
    provider_id: str
    route: str
    model_id: str | None
    status: str
    reason: str


ENVIRONMENT_KEYS = {
    "ollama": "OLLAMA_API_KEY",
    "einfra": "CERIT_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
}


def audit_catalog(
    catalog_path: Path,
    *,
    update: bool = False,
    provider_filter: str | None = None,
    show_models: bool = False,
    sync_models: bool = False,
    discovered_path: Path | None = None,
    fetch: Callable[[str, dict[str, str]], tuple[int, Any]] | None = None,
    executable_exists: Callable[[str], bool] = lambda executable: shutil.which(executable) is not None,
) -> tuple[list[AuditResult], dict[str, Any]]:
    """Audit routes and listed models, optionally writing confirmed statuses.

    A missing credential or executable is reported as ``unknown`` because it
    does not prove that the provider is unavailable for the user.
    """
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(catalog, dict) or not isinstance(catalog.get("providers"), list):
        raise TypeError("catalog must contain a providers list")
    fetch = fetch or fetch_json
    results: list[AuditResult] = []

    for provider in catalog["providers"]:
        if not isinstance(provider, dict):
            continue
        provider_id = str(provider.get("id", "unknown"))
        if provider_filter and provider_id != provider_filter:
            continue
        methods = provider.get("access_methods", [])
        if not isinstance(methods, list):
            continue
        for method in methods:
            if not isinstance(method, dict):
                continue
            method_id = str(method.get("id", "unknown"))
            if method_id == "cli":
                results.extend(_audit_cli(provider_id, method, executable_exists))
            elif method_id in {"api", "openai-compatible"}:
                results.extend(_audit_api(provider, method, fetch, show_models=show_models or discovered_path is not None))

    if update:
        _apply_results(catalog, results)
        if sync_models:
            _sync_discovered_models(catalog, results)
        catalog["last_audited"] = datetime.now(UTC).date().isoformat()
        catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False, allow_unicode=True), encoding="utf-8")
    if discovered_path is not None:
        _write_discovered_snapshot(discovered_path, results)
    return results, catalog


def fetch_json(url: str, headers: dict[str, str]) -> tuple[int, Any]:
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=15) as response:
            return response.status, yaml.safe_load(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, None
    except (URLError, TimeoutError, OSError):
        return 0, None


def _audit_cli(provider_id: str, method: dict[str, Any], executable_exists: Callable[[str], bool]) -> list[AuditResult]:
    executable = str(method.get("executable", ""))
    if not executable:
        return [AuditResult(provider_id, "cli", None, "unknown", "catalog route has no executable")]
    if not executable_exists(executable):
        return [AuditResult(provider_id, "cli", None, "unavailable", f"executable not found: {executable}")]
    return [AuditResult(provider_id, "cli", None, "available", f"executable found: {executable}")]


def _audit_api(
    provider: dict[str, Any],
    method: dict[str, Any],
    fetch: Callable[[str, dict[str, str]], tuple[int, Any]],
    *,
    show_models: bool = False,
) -> list[AuditResult]:
    provider_id = str(provider.get("id", "unknown"))
    discovery = method.get("model_discovery")
    if not isinstance(discovery, dict) or discovery.get("method") != "GET":
        return [AuditResult(provider_id, str(method.get("id", "unknown")), None, "unknown", "no GET model discovery route")]
    env_name = ENVIRONMENT_KEYS.get(provider_id)
    credential = os.environ.get(env_name, "") if env_name else ""
    if provider_id not in {"ollama"} and not credential:
        return [AuditResult(provider_id, str(method.get("id", "unknown")), None, "unknown", f"missing {env_name or 'provider credential'}")]
    headers = {"accept": "application/json"}
    if credential:
        if provider_id == "anthropic":
            headers.update({"x-api-key": credential, "anthropic-version": "2023-06-01"})
        else:
            headers["authorization"] = f"Bearer {credential}"
    status_code, body = fetch(str(discovery["endpoint"]), headers)
    route = str(method.get("id", "unknown"))
    if status_code != 200:
        reason = f"model discovery returned HTTP {status_code}" if status_code else "model discovery connection failed"
        return [AuditResult(provider_id, route, None, "unavailable", reason)]
    discovered = _model_ids(body)
    models = provider.get("models", [])
    results = [AuditResult(provider_id, route, None, "available", f"discovered {len(discovered)} model(s)")]
    listed_ids = {
        str(model.get("id"))
        for model in provider.get("models", [])
        if isinstance(model, dict) and model.get("id")
    }
    if show_models:
        results.extend(
            AuditResult(provider_id, route, model_id, "available", "exact model discovered; ranked by capability/name heuristic")
            for model_id in sorted(discovered - listed_ids, key=_model_sort_key)
        )
    if isinstance(models, list) and discovered:
        for model in models:
            if not isinstance(model, dict) or not model.get("id"):
                continue
            model_id = str(model["id"])
            aliases = {model_id}
            if model.get("resolves_to"):
                aliases.add(str(model["resolves_to"]))
            present = bool(aliases & discovered)
            if present:
                model_status = "available"
                reason = "model returned by provider"
            elif model.get("kind") == "maintained-alias":
                # Providers may expose aliases through routing without listing
                # the alias in model metadata. Discovery alone cannot prove an
                # alias is unavailable; a live chat probe is required.
                model_status = "unknown"
                reason = "maintained alias not listed; requires live chat probe"
            else:
                model_status = "unavailable"
                reason = "model not returned by provider"
            results.append(AuditResult(provider_id, route, model_id, model_status, reason))
    return results


def _model_ids(body: Any) -> set[str]:
    ids: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, str):
            ids.add(value)
        elif isinstance(value, list):
            for entry in value:
                visit(entry)
        elif isinstance(value, dict):
            # CERIT model metadata may use a UUID as `id` and expose the
            # actual model selector separately as `name` or `model_name`.
            direct = (
                value.get("name")
                or value.get("model_name")
                or value.get("model")
                or value.get("slug")
            )
            if not direct and value.get("id") and not _looks_like_uuid(str(value["id"])):
                direct = value["id"]
            if direct:
                ids.add(str(direct))
            for key in ("data", "models", "items", "results", "model_info"):
                if key in value:
                    visit(value[key])

    visit(body)
    return ids


def _looks_like_uuid(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", value.lower()))


def _model_sort_key(model_id: str) -> tuple[int, int, int, str]:
    """Rank names for readable output; the provider remains source of truth."""
    name = model_id.lower()
    family_rank = 0
    for family, rank in (
        ("deepseek", 80),
        ("kimi", 75),
        ("glm", 70),
        ("qwen", 65),
        ("gpt-oss", 60),
        ("llama", 50),
        ("mistral", 45),
    ):
        if family in name:
            family_rank = rank
            break
    capability_rank = 0
    for marker, rank in (("thinking", 30), ("reasoning", 30), ("pro", 25), ("agentic", 20), ("coder", 15), ("instruct", 10)):
        if marker in name:
            capability_rank = max(capability_rank, rank)
    versions = [int(value) for value in re.findall(r"\d+", name)]
    version_rank = int("".join(f"{value:03d}" for value in versions[-2:])) if versions else 0
    return (-family_rank, -capability_rank, -version_rank, name)


def _apply_results(catalog: dict[str, Any], results: list[AuditResult]) -> None:
    by_model = {(result.provider_id, result.model_id): result for result in results if result.model_id}
    for provider in catalog.get("providers", []):
        if not isinstance(provider, dict):
            continue
        provider_id = str(provider.get("id", ""))
        for model in provider.get("models", []):
            if not isinstance(model, dict):
                continue
            result = by_model.get((provider_id, str(model.get("id", ""))))
            if result and result.status in {"available", "unavailable"}:
                model["status"] = result.status


def _sync_discovered_models(catalog: dict[str, Any], results: list[AuditResult]) -> None:
    providers = {
        str(provider.get("id")): provider
        for provider in catalog.get("providers", [])
        if isinstance(provider, dict)
    }
    for result in results:
        if result.model_id is None or "exact model discovered" not in result.reason:
            continue
        provider = providers.get(result.provider_id)
        if provider is None:
            continue
        models = provider.setdefault("models", [])
        if any(isinstance(model, dict) and model.get("id") == result.model_id for model in models):
            continue
        model_type = _model_type(result.model_id)
        capability = {
            "chat/reason": "chat",
            "embedding": "embedding",
            "reranker": "reranking",
            "speech": "speech",
            "image": "image",
        }.get(model_type, "specialized")
        models.append({
            "id": result.model_id,
            "status": result.status,
            "kind": "discovered",
            "capabilities": [capability],
        })


def _write_discovered_snapshot(path: Path, results: list[AuditResult]) -> None:
    providers: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        if result.model_id is None or "exact model discovered" not in result.reason:
            continue
        providers[result.provider_id].append({
            "id": result.model_id,
            "status": result.status,
            "kind": "discovered",
            "category": _model_type(result.model_id),
            "suitability": _suitability(result.model_id),
            "route": result.route,
            "pricing": "unknown",
        })
    snapshot = {
        "snapshot_version": 1,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "providers": [{"id": provider_id, "models": models} for provider_id, models in sorted(providers.items())],
    }
    path.write_text(yaml.safe_dump(snapshot, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _suitability(model_id: str) -> dict[str, str]:
    """Return conservative task hints from model naming/category signals."""
    category = _model_type(model_id)
    name = model_id.lower()
    if category == "embedding":
        tasks = ["semantic-search", "rag", "similarity"]
    elif category == "reranker":
        tasks = ["search-ranking", "rag"]
    elif category == "speech":
        tasks = ["transcription", "speech"]
    elif category == "image":
        tasks = ["image-generation"]
    else:
        tasks = ["chat", "summarization", "translation"]
        if any(marker in name for marker in ("coder", "code", "qwen", "deepseek")):
            tasks.append("coding")
        if any(marker in name for marker in ("thinking", "reason", "pro", "deepseek", "kimi", "glm")):
            tasks.append("reasoning")
        if any(marker in name for marker in ("agentic", "tool")):
            tasks.append("tools")
    return {"tasks": tasks, "basis": "capability/name heuristic; validate with task-specific evals"}


def format_results(results: list[AuditResult], catalog: dict[str, Any] | None = None, *, show_routes: bool = False) -> str:
    providers = {
        str(provider.get("id")): provider
        for provider in (catalog or {}).get("providers", [])
        if isinstance(provider, dict)
    }
    model_results = [result for result in results if result.model_id]
    if not model_results:
        return "no model results; check credentials and discovery routes"
    if show_routes:
        lines = []
        for result in results:
            subject = f"{result.provider_id}/{result.model_id}" if result.model_id else result.provider_id
            lines.append(f"{result.status:11} {subject:40} {result.route}: {result.reason}")
        return "\n".join(lines)

    groups: dict[tuple[str, str], list[tuple[AuditResult, dict[str, Any]]]] = defaultdict(list)
    for result in model_results:
        provider = providers.get(result.provider_id, {})
        model_type = _model_type(result.model_id or "")
        groups[(result.provider_id, model_type)].append((result, provider))

    lines: list[str] = []
    category_order = {"chat/reason": 0, "embedding": 1, "reranker": 2, "speech": 3, "image": 4, "specialized": 5}
    for (provider_id, model_type), entries in sorted(groups.items(), key=lambda item: (item[0][0], category_order.get(item[0][1], 9), item[0][1])):
        lines.extend([
            f"[{provider_id} / {model_type}]",
            "model                                 source     status       input/1M  output/1M",
            "-" * 87,
        ])
        for result, provider in entries:
            pricing = _pricing_for_model(provider, result.model_id or "")
            per_token = pricing.get("per_1m_tokens") or {}
            source = _model_source(provider, result.model_id or "")
            lines.append(
                f"{(result.model_id or '')[:35]:35} {source:10} {result.status:12} "
                f"{_price(per_token.get('input'), pricing):12} {_price(per_token.get('output'), pricing):12}"
            )
        lines.append("")
    return "\n".join(lines)


def _price(value: Any, pricing: dict[str, Any] | None = None) -> str:
    if value is not None:
        return f"${value:g}"
    billing_model = (pricing or {}).get("billing_model")
    if billing_model == "local":
        return "$0"
    if billing_model == "institutional":
        return "institutional"
    if billing_model in {"usage-or-subscription", "subscription-or-api"}:
        return "varies"
    return "unknown"


def _pricing_for_model(provider: dict[str, Any], model_id: str) -> dict[str, Any]:
    for model in provider.get("models", []):
        if not isinstance(model, dict):
            continue
        if model.get("id") == model_id or model.get("resolves_to") == model_id:
            model_pricing = model.get("pricing")
            if isinstance(model_pricing, dict):
                return model_pricing
    pricing = provider.get("pricing", {})
    return pricing if isinstance(pricing, dict) else {}


def _model_source(provider: dict[str, Any], model_id: str) -> str:
    for model in provider.get("models", []):
        if isinstance(model, dict) and model.get("id") == model_id:
            return "discovered" if model.get("kind") == "discovered" else "curated"
    return "discovered"


def _model_type(model_id: str) -> str:
    name = model_id.lower()
    if any(marker in name for marker in ("embed", "e5-", "bge-", "mxbai")):
        return "embedding"
    if "rerank" in name:
        return "reranker"
    if any(marker in name for marker in ("whisper", "transcri", "tts", "audio")):
        return "speech"
    if "image" in name:
        return "image"
    return "chat/reason"
