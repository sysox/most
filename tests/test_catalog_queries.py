import json
from pathlib import Path

from most.catalog_queries import list_aliases, list_mcp_servers
from most.cli import main


def test_list_aliases_reads_curated_catalog_without_credentials():
    aliases = list_aliases(Path("ai-catalog.yaml"), "einfra")
    assert aliases
    assert aliases[0]["provider"] == "einfra"
    assert all(item["resolves_to"] for item in aliases)


def test_list_mcp_servers_uses_cli_registry():
    servers = list_mcp_servers()
    assert {item["name"] for item in servers} >= {"ddg_search", "DocFork"}
    assert all(item["url"].endswith("/mcp") for item in servers)


def test_metadata_queries_are_json_cli_entrypoints(capsys):
    assert main(["list-aliases", "--provider", "einfra"]) == 0
    aliases = json.loads(capsys.readouterr().out)
    assert all(item["provider"] == "einfra" for item in aliases)

    assert main(["list-mcp-servers"]) == 0
    servers = json.loads(capsys.readouterr().out)
    assert any(item["name"] == "ddg_search" for item in servers)
