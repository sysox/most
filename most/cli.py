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
