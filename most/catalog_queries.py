"""Read-only catalog and MCP metadata queries for downstream integrations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .catalog_schema import validate_catalog


def list_aliases(catalog_path: Path = Path("ai-catalog.yaml"), provider_id: str | None = None) -> list[dict[str, Any]]:
    """Return maintained model aliases without inspecting credentials."""
    catalog = validate_catalog(yaml.safe_load(catalog_path.read_text(encoding="utf-8")))
    aliases: list[dict[str, Any]] = []
    for provider in catalog["providers"]:
        current_provider = str(provider["id"])
        if provider_id and current_provider != provider_id:
            continue
        for model in provider.get("models", []):
            if not isinstance(model, dict) or model.get("kind") != "maintained-alias":
                continue
            aliases.append({
                "id": model["id"],
                "provider": current_provider,
                "resolves_to": model.get("resolves_to"),
                "capabilities": list(model.get("capabilities", [])),
            })
    return sorted(aliases, key=lambda item: (str(item["provider"]), str(item["id"])))


def list_mcp_servers() -> list[dict[str, str]]:
    """Return the configured MCP server names from the CLI single source."""
    from .cli_chat import MCP_SERVERS

    return [{"name": name, "url": MCP_SERVERS[name]} for name in sorted(MCP_SERVERS)]
