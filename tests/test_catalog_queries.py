import json
from pathlib import Path

import yaml

from most.catalog_queries import list_aliases, list_mcp_servers
from most.cli import main
from most.cli_chat import MCP_SERVERS


def test_list_aliases_reads_curated_catalog_without_credentials():
    catalog_path = Path("ai-catalog.yaml")
    aliases = list_aliases(catalog_path, "einfra")
    all_aliases = list_aliases(catalog_path)
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    expected = {
        (provider["id"], model["id"])
        for provider in catalog["providers"]
        for model in provider.get("models", [])
        if model.get("kind") == "maintained-alias"
    }
    assert aliases
    assert aliases[0]["provider"] == "einfra"
    assert aliases == [item for item in all_aliases if item["provider"] == "einfra"]
    assert {(item["provider"], item["id"]) for item in aliases} == {
        entry for entry in expected if entry[0] == "einfra"
    }
    assert all(item["resolves_to"] for item in aliases)


def test_list_mcp_servers_uses_cli_registry():
    servers = list_mcp_servers()
    assert {item["name"] for item in servers} == set(MCP_SERVERS)
    assert all(item["url"].endswith("/mcp") for item in servers)


def test_metadata_queries_are_json_cli_entrypoints(capsys):
    assert main(["list-aliases", "--provider", "einfra"]) == 0
    aliases = json.loads(capsys.readouterr().out)
    assert all(item["provider"] == "einfra" for item in aliases)

    assert main(["list-mcp-servers"]) == 0
    servers = json.loads(capsys.readouterr().out)
    assert any(item["name"] == "ddg_search" for item in servers)
