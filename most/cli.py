from __future__ import annotations

import argparse
import json
from pathlib import Path

from .adapters import create_default_registry
from .models import AIConfiguration, AIRequest, IntermediateResult, SessionMode
from .openai_compatible import normalize_response
from .services import ConfigurationService, ExecutionManager, SessionService
from .workspace import WorkspaceService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="most", description="File-backed multi-provider AI core")
    parser.add_argument("--data-root", type=Path, default=Path("application-data"))
    subparsers = parser.add_subparsers(dest="command", required=True)
    session = subparsers.add_parser("create-session")
    session.add_argument("title")
    session.add_argument("--workspace", action="store_true")
    configuration = subparsers.add_parser("create-configuration")
    configuration.add_argument("name")
    configuration.add_argument("--provider", default="custom")
    configuration.add_argument("--access-method", default="openai-compatible")
    subparsers.add_parser("list-sessions")
    subparsers.add_parser("list-configurations")
    execution = subparsers.add_parser("inspect-execution")
    execution.add_argument("execution_id")
    workspace = subparsers.add_parser("inspect-workspace")
    workspace.add_argument("repository", type=Path)
    workspace.add_argument("--diff", action="store_true")
    workspace.add_argument("--compatibility", action="store_true")
    workspace.add_argument("--history", action="store_true")
    chat = subparsers.add_parser("chat", help="communicate with a local OpenAI-compatible runtime")
    chat.add_argument("prompt", nargs="?")
    chat.add_argument("--model", default="granite4.1:3b")
    chat.add_argument("--base-url", default="http://127.0.0.1:11434/v1")
    chat.add_argument("--title", default="Local AI chat")
    cerit_chat = subparsers.add_parser("cerit-chat", help="communicate with CERIT-SC through its OpenAI-compatible API")
    cerit_chat.add_argument("prompt", nargs="?")
    cerit_chat.add_argument("--model", default="mini", help="CERIT model name or maintained alias")
    cerit_chat.add_argument("--base-url", default="https://llm.ai.e-infra.cz/v1")
    cerit_chat.add_argument("--api-key-env", default="CERIT_API_KEY", help="environment variable containing the CERIT API key")
    cerit_chat.add_argument("--title", default="CERIT AI chat")
    gpt_chat = subparsers.add_parser("gpt-chat", help="communicate with OpenAI through the official Responses API")
    gpt_chat.add_argument("prompt", nargs="?")
    gpt_chat.add_argument("--model", default="gpt-5.6")
    gpt_chat.add_argument("--api-key-env", default="OPENAI_API_KEY", help="environment variable containing the OpenAI API key")
    gpt_chat.add_argument("--base-url", default="https://api.openai.com/v1")
    gpt_chat.add_argument("--title", default="GPT AI chat")
    catalog_audit = subparsers.add_parser("catalog-audit", help="check catalog routes and model availability")
    catalog_audit.add_argument("--catalog", type=Path, default=Path("ai-catalog.yaml"))
    catalog_audit.add_argument("--provider", help="limit the audit to one provider, e.g. einfra")
    catalog_audit.add_argument("--show-models", action="store_true", help="print exact model IDs returned by discovery")
    catalog_audit.add_argument("--sync-models", action="store_true", help="add discovered models to the catalog; requires --update")
    catalog_audit.add_argument("--discovered", type=Path, default=Path("ai-discovered.yaml"), help="generated dynamic-model snapshot")
    catalog_audit.add_argument("--no-discovered", action="store_true", help="do not write the dynamic-model snapshot")
    catalog_audit.add_argument("--show-routes", action="store_true", help="show internal access routes instead of the model table")
    pricing = subparsers.add_parser("catalog-pricing", help="validate and apply source-backed model pricing")
    pricing.add_argument("--source", type=Path, required=True, help="YAML pricing update file")
    pricing.add_argument("--catalog", type=Path, default=Path("ai-catalog.yaml"))
    pricing.add_argument("--update", action="store_true", help="write validated prices to the catalog")
    catalog_audit.add_argument("--update", action="store_true", help="write confirmed availability statuses to the catalog")
    catalog_refresh = subparsers.add_parser("catalog-refresh", help="refresh dynamic model inventory and route status")
    catalog_refresh.add_argument("--catalog", type=Path, default=Path("ai-catalog.yaml"))
    catalog_refresh.add_argument("--provider", help="limit the refresh to one provider")
    catalog_refresh.add_argument("--show-models", action="store_true", help="print discovered model IDs")
    catalog_refresh.add_argument("--update", action="store_true", help="update curated availability statuses")
    catalog_refresh.add_argument("--sync-models", action="store_true", help="copy discovered models into the curated catalog")
    catalog_refresh.add_argument("--discovered", type=Path, default=Path("ai-discovered.yaml"))
    catalog_refresh.add_argument("--no-discovered", action="store_true")
    catalog_refresh.add_argument("--show-routes", action="store_true")
    browser_chat = subparsers.add_parser("browser-chat", help="communicate through a logged-in browser session")
    browser_chat.add_argument("provider", choices=("chatgpt", "gemini", "claude", "cerit"))
    browser_chat.add_argument("prompt", nargs="?")
    browser_chat.add_argument("--title", default="Browser AI chat")
    browser_chat.add_argument("--headless", action="store_true")
    browser_chat.add_argument("--manual", action="store_true", help="use a normal browser with manual copy/paste")
    cli_chat = subparsers.add_parser("cli-chat", help="communicate through an installed provider CLI")
    cli_chat.add_argument("provider", choices=("codex", "claude", "gemini", "agy"))
    cli_chat.add_argument("prompt", nargs="?")
    cli_chat.add_argument("--title", default="Provider CLI chat")
    cli_chat.add_argument("--allow-unknown-connectivity", action="store_true", help="approve opaque provider CLI network routing")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "create-session":
        mode = SessionMode.WORKSPACE if args.workspace else SessionMode.COMMUNICATION
        session = SessionService(args.data_root).create(args.title, mode)
        print(session.id)
        return 0
    if args.command == "create-configuration":
        configuration = AIConfiguration(name=args.name, provider_id=args.provider, access_method_id=args.access_method)
        ConfigurationService(args.data_root).save(configuration)
        print(configuration.id)
        return 0
    if args.command == "list-sessions":
        print(json.dumps(SessionService(args.data_root).list(), indent=2, default=str))
        return 0
    if args.command == "list-configurations":
        print(json.dumps(ConfigurationService(args.data_root).list(), indent=2, default=str))
        return 0
    if args.command == "inspect-workspace":
        service = WorkspaceService(args.data_root, args.repository)
        result = service.compatibility_report() if args.compatibility else service.inspect()
        if args.diff and result["is_repository"]:
            result["diff"] = service.git.diff()
        if args.history:
            result["history"] = service.history()
        print(json.dumps(result, indent=2, default=str))
        return 0
    if args.command == "chat":
        return run_chat(args)
    if args.command == "cerit-chat":
        return run_cerit_chat(args)
    if args.command == "gpt-chat":
        return run_gpt_chat(args)
    if args.command in {"catalog-audit", "catalog-refresh"}:
        from .catalog_audit import audit_catalog, format_results
        if args.sync_models and not args.update:
            raise SystemExit("--sync-models requires --update")
        results, catalog = audit_catalog(
            args.catalog,
            update=args.update,
            provider_filter=args.provider,
            show_models=args.show_models or args.sync_models,
            sync_models=args.sync_models,
            discovered_path=None if args.no_discovered else args.discovered,
        )
        print(format_results(results, catalog, show_routes=args.show_routes))
        if args.update:
            print(f"updated: {args.catalog}")
        return 0 if all(result.status != "unavailable" for result in results) else 1
    if args.command == "catalog-pricing":
        from .catalog_pricing import apply_pricing_updates
        apply_pricing_updates(args.catalog, args.source, update=args.update)
        print("pricing update validated")
        if args.update:
            print(f"updated: {args.catalog}")
        return 0
    if args.command == "browser-chat":
        if args.manual:
            from .manual_browser_chat import run_manual_browser_chat
            return run_manual_browser_chat(args)
        from .browser_chat import run_browser_chat
        return run_browser_chat(args)
    if args.command == "cli-chat":
        from .cli_chat import run_cli_chat
        return run_cli_chat(args)
    if args.command == "inspect-execution":
        execution_root = args.data_root / "executions"
        direct_metadata = execution_root / args.execution_id / "metadata.yaml"
        direct_events = execution_root / args.execution_id / "events.jsonl"
        metadata = direct_metadata if direct_metadata.exists() else next(execution_root.glob(f"*/{args.execution_id}/metadata.yaml"), None)
        events = direct_events if direct_events.exists() else next(execution_root.glob(f"*/{args.execution_id}/events.jsonl"), None)
        if metadata is None:
            raise SystemExit(f"execution not found: {args.execution_id}")
        import yaml
        result = {"metadata": yaml.safe_load(metadata.read_text(encoding="utf-8"))}
        result["events"] = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()] if events else []
        print(json.dumps(result, indent=2, default=str))
        return 0
    return 2


def run_chat(args: argparse.Namespace, *, registry=None) -> int:
    """Run a journaled local chat session through an OpenAI-compatible adapter."""
    root = args.data_root
    sessions = SessionService(root)
    session = sessions.create(args.title)
    configuration = AIConfiguration(
        name=f"Local: {args.model}",
        provider_id="local",
        access_method_id="openai-compatible",
        model_reference=args.model,
        location="local",
        network="localhost",
        adapter_options={"base_url": args.base_url},
    )
    ConfigurationService(root).save(configuration)
    manager = ExecutionManager(root)
    adapter = (registry or create_default_registry()).get("openai-compatible")
    messages: list[dict[str, str]] = []
    prompt = args.prompt
    while True:
        if prompt is None:
            try:
                prompt = input("you> ")
            except EOFError:
                break
        prompt = prompt.strip()
        if not prompt:
            prompt = None
            continue
        if prompt.lower() in {"/exit", "/quit"}:
            break
        messages.append({"role": "user", "content": prompt})
        interaction = sessions.append_interaction(session, configuration.id, len(messages))
        request = AIRequest(
            session_id=session.id,
            interaction_id=interaction.id,
            configuration_id=configuration.id,
            messages=list(messages),
        )
        execution = manager.prepare(request, configuration, session)
        execution, response = manager.execute(execution, request, configuration, adapter)
        normalized = normalize_response(response)
        content = "".join(
            str(part.get("text", ""))
            for part in normalized["content_parts"]
            if isinstance(part, dict)
        )
        result = IntermediateResult(
            session_id=session.id,
            interaction_id=interaction.id,
            execution_id=execution.id,
            sequence_number=len(messages),
            result_type="response",
            parent_result_id=session.active_result_id,
        )
        sessions.add_result(result, content)
        session.active_result_id = result.id
        messages.append({"role": "assistant", "content": content})
        print(f"assistant> {content}")
        if args.prompt is not None:
            break
        prompt = None
    print(f"session: {session.id}")
    return 0


def run_cerit_chat(args: argparse.Namespace, *, registry=None) -> int:
    """Run a journaled CERIT-SC chat using an environment-provided API key."""
    import os

    credential = os.environ.get(args.api_key_env)
    if not credential:
        raise SystemExit(f"missing CERIT API key; set ${args.api_key_env} without putting it in configuration files")
    root = args.data_root
    sessions = SessionService(root)
    session = sessions.create(args.title)
    configuration = AIConfiguration(
        name=f"CERIT: {args.model}", provider_id="cerit", access_method_id="openai-compatible",
        model_reference=args.model, location="remote-public", network="public-internet",
        adapter_options={"base_url": args.base_url},
    )
    ConfigurationService(root).save(configuration)
    manager = ExecutionManager(root)
    adapter = (registry or create_default_registry()).get("openai-compatible")
    messages: list[dict[str, str]] = []
    prompt = args.prompt
    while True:
        if prompt is None:
            try:
                prompt = input("you> ")
            except EOFError:
                break
        prompt = prompt.strip()
        if not prompt:
            prompt = None
            continue
        if prompt.lower() in {"/exit", "/quit"}:
            break
        messages.append({"role": "user", "content": prompt})
        interaction = sessions.append_interaction(session, configuration.id, len(messages))
        request = AIRequest(session_id=session.id, interaction_id=interaction.id, configuration_id=configuration.id, messages=list(messages))
        execution = manager.prepare(request, configuration, session)
        execution, response = manager.execute(execution, request, configuration, adapter, credential_handle=credential)
        normalized = normalize_response(response)
        content = "".join(str(part.get("text", "")) for part in normalized["content_parts"] if isinstance(part, dict))
        result = IntermediateResult(
            session_id=session.id, interaction_id=interaction.id, execution_id=execution.id,
            sequence_number=len(messages), result_type="response", parent_result_id=session.active_result_id,
        )
        sessions.add_result(result, content)
        session.active_result_id = result.id
        messages.append({"role": "assistant", "content": content})
        print(f"assistant> {content}")
        if args.prompt is not None:
            break
        prompt = None
    print(f"session: {session.id}")
    return 0


def run_gpt_chat(args: argparse.Namespace, *, registry=None) -> int:
    """Run a journaled OpenAI Responses API chat using an environment key."""
    import os

    from .openai_api import normalize_response as normalize_openai_response

    credential = os.environ.get(args.api_key_env)
    if not credential:
        raise SystemExit(f"missing OpenAI API key; set ${args.api_key_env} without putting it in configuration files")
    root = args.data_root
    sessions = SessionService(root)
    session = sessions.create(args.title)
    configuration = AIConfiguration(
        name=f"OpenAI: {args.model}", provider_id="openai", access_method_id="openai-api",
        model_reference=args.model, location="provider-cloud", network="public-internet",
        adapter_options={"base_url": args.base_url},
    )
    ConfigurationService(root).save(configuration)
    manager = ExecutionManager(root)
    adapter = (registry or create_default_registry()).get("openai-api")
    messages: list[dict[str, str]] = []
    prompt = args.prompt
    while True:
        if prompt is None:
            try:
                prompt = input("you> ")
            except EOFError:
                break
        prompt = prompt.strip()
        if not prompt:
            prompt = None
            continue
        if prompt.lower() in {"/exit", "/quit"}:
            break
        messages.append({"role": "user", "content": prompt})
        interaction = sessions.append_interaction(session, configuration.id, len(messages))
        request = AIRequest(session_id=session.id, interaction_id=interaction.id, configuration_id=configuration.id, messages=list(messages))
        execution = manager.prepare(request, configuration, session)
        execution, response = manager.execute(execution, request, configuration, adapter, credential_handle=credential)
        normalized = normalize_openai_response(response)
        content = "".join(str(part.get("text", "")) for part in normalized["content_parts"] if isinstance(part, dict))
        result = IntermediateResult(session_id=session.id, interaction_id=interaction.id, execution_id=execution.id,
                                    sequence_number=len(messages), result_type="response", parent_result_id=session.active_result_id)
        sessions.add_result(result, content)
        session.active_result_id = result.id
        messages.append({"role": "assistant", "content": content})
        print(f"assistant> {content}")
        if args.prompt is not None:
            break
        prompt = None
    print(f"session: {session.id}")
    return 0
