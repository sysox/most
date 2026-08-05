from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
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
    cerit_chat.add_argument("--thinking", dest="thinking", action="store_true", default=None,
                            help="enable model reasoning when supported")
    cerit_chat.add_argument("--no-thinking", dest="thinking", action="store_false",
                            help="disable model reasoning when supported")
    cerit_chat.add_argument("--sensitivity-tier", choices=("normal", "sensitive"), default="normal",
                            help="workload sensitivity; sensitive e-INFRA models must be verified on-premise")
    cerit_chat.add_argument("--catalog", type=Path, default=Path("ai-catalog.yaml"))
    cerit_chat.add_argument("--profile")
    cerit_chat.add_argument("--pipeline-id")
    cerit_chat.add_argument("--stage-index", type=int)
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
    options = subparsers.add_parser("catalog-options", help="list unified model and route options")
    options.add_argument("--catalog", type=Path, default=Path("ai-catalog.yaml"))
    options.add_argument("--discovered", type=Path, default=Path("ai-discovered.yaml"))
    options.add_argument("--provider")
    options.add_argument("--capability", help="show only models supporting a capability, e.g. chat, embedding, image, speech")
    options.add_argument("--json", action="store_true")
    options.add_argument("--no-refresh", action="store_true")
    options.add_argument("--max-age-hours", type=float, default=24.0)
    unified = subparsers.add_parser("ai-chat", help="chat through the selected catalog model and route")
    unified.add_argument("prompt", nargs="?")
    unified.add_argument("--provider")
    unified.add_argument("--model", required=True)
    unified.add_argument("--route", default="auto", choices=("auto", "openai-compatible", "api", "cli"))
    unified.add_argument("--catalog", type=Path, default=Path("ai-catalog.yaml"))
    unified.add_argument("--discovered", type=Path, default=Path("ai-discovered.yaml"))
    unified.add_argument("--title", default="Unified AI chat")
    unified.add_argument("--no-refresh", action="store_true")
    unified.add_argument("--max-age-hours", type=float, default=24.0)
    unified.add_argument("--thinking", dest="thinking", action="store_true", default=None,
                         help="enable model reasoning when supported")
    unified.add_argument("--no-thinking", dest="thinking", action="store_false",
                         help="disable model reasoning when supported")
    unified.add_argument("--sensitivity-tier", choices=("normal", "sensitive"), default="normal",
                         help="workload sensitivity; sensitive e-INFRA models must be verified on-premise")
    unified.add_argument("--profile")
    unified.add_argument("--pipeline-id")
    unified.add_argument("--stage-index", type=int)
    embed = subparsers.add_parser("ai-embed", help="create an embedding vector from text")
    _add_capability_task_args(embed, "embedding", output_modality="embedding")
    embed.add_argument("--input", type=Path, required=True, help="UTF-8 text file to embed")
    embed.add_argument("--output", type=Path, help="write the vector as JSON")
    image = subparsers.add_parser("ai-image", help="generate an image from a prompt")
    _add_capability_task_args(image, "image", output_modality="image")
    image.add_argument("prompt")
    image.add_argument("--output", type=Path, default=Path("generated-image.bin"))
    speech = subparsers.add_parser("ai-speech", help="synthesize speech from text")
    _add_capability_task_args(speech, "speech", output_modality="audio")
    speech.add_argument("text")
    speech.add_argument("--output", type=Path, default=Path("generated-speech.bin"))
    image_analysis = subparsers.add_parser("ai-image-analyze", help="analyze an image with a vision-capable chat model")
    _add_capability_task_args(image_analysis, "chat", input_modality="image")
    image_analysis.add_argument("--input", type=Path, required=True, help="image file to analyze")
    image_analysis.add_argument("prompt", nargs="?", default="Describe this image.")
    transcription = subparsers.add_parser("ai-transcribe", help="transcribe audio to text")
    _add_capability_task_args(transcription, "transcription", input_modality="audio", output_modality="text")
    transcription.add_argument("--input", type=Path, required=True, help="audio file to transcribe")
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
    health = subparsers.add_parser("catalog-health", help="recheck models recorded after provider failures")
    health.add_argument("--catalog", type=Path, default=Path("ai-catalog.yaml"))
    health.add_argument("--discovered", type=Path, default=Path("ai-discovered.yaml"))
    credentials = subparsers.add_parser("credentials", help="manage provider API keys in the OS keyring")
    credential_commands = credentials.add_subparsers(dest="credential_command", required=True)
    credential_set = credential_commands.add_parser("set", help="store or replace a provider API key")
    credential_set.add_argument("provider")
    credential_set.add_argument(
        "--from-env",
        action="store_true",
        help="copy the provider key from its standard environment variable",
    )
    credential_remove = credential_commands.add_parser("remove", help="remove a provider API key")
    credential_remove.add_argument("provider")
    credential_commands.add_parser("list", help="list supported provider credential names")
    browser_chat = subparsers.add_parser("browser-chat", help="communicate through a logged-in browser session")
    browser_chat.add_argument("provider", choices=("chatgpt", "gemini", "claude", "cerit"))
    browser_chat.add_argument("prompt", nargs="?")
    browser_chat.add_argument("--title", default="Browser AI chat")
    browser_chat.add_argument("--headless", action="store_true")
    browser_chat.add_argument("--manual", action="store_true", help="use a normal browser with manual copy/paste")
    browser_chat.add_argument("--profile", help="named persistent browser login profile (default: provider name)")
    browser_chat.add_argument("--sensitivity-tier", choices=("normal", "sensitive"), default="normal",
                              help="workload sensitivity; sensitive workloads cannot use browser-chat")
    policy_check = subparsers.add_parser("policy-check", help="preflight a route policy without starting a provider call")
    policy_check.add_argument("--sensitivity-tier", choices=("normal", "sensitive"), required=True)
    policy_check.add_argument("--route", required=True, choices=("browser-chat", "cli-chat", "ai-chat", "cerit-chat"))
    policy_check.add_argument("--provider", required=True)
    policy_check.add_argument("--model")
    policy_check.add_argument("--catalog", type=Path, default=Path("ai-catalog.yaml"))
    cli_chat = subparsers.add_parser("cli-chat", help="communicate through an installed provider CLI")
    cli_chat.add_argument("provider", nargs="?", choices=("codex", "claude", "gemini", "agy", "opencode"))
    cli_chat.add_argument("--agent", choices=("codex", "claude", "gemini", "agy", "opencode"),
                          help="named alias for the provider positional argument")
    cli_chat.add_argument("prompt", nargs="?")
    cli_chat.add_argument("--title", default="Provider CLI chat")
    cli_chat.add_argument("--allow-unknown-connectivity", action="store_true", help="approve opaque provider CLI network routing")
    cli_chat.add_argument("--writable", action="store_true",
                          help="opt into provider file edits; target a repository with --workspace")
    cli_chat.add_argument("--workspace", type=Path,
                          help="explicit working directory; required to edit a target repository")
    cli_chat.add_argument("--credential-provider", choices=("einfra",),
                          help="route CLI authentication through a stored provider credential")
    cli_chat.add_argument("--model", help="provider model alias when using --credential-provider")
    cli_chat.add_argument("--sensitivity-tier", choices=("normal", "sensitive"), default="normal",
                          help="workload sensitivity; sensitive e-INFRA models must be verified on-premise")
    cli_chat.add_argument("--catalog", type=Path, default=Path("ai-catalog.yaml"))
    cli_chat.add_argument("--profile")
    cli_chat.add_argument("--pipeline-id")
    cli_chat.add_argument("--stage-index", type=int)
    cli_chat.add_argument("--mcp-server", action="append", metavar="NAME",
                          help="attach an e-INFRA MCP server to Claude (repeatable)")
    return parser


def _add_capability_task_args(command: argparse.ArgumentParser, capability: str, *, input_modality: str | None = None, output_modality: str | None = None) -> None:
    command.set_defaults(required_capability=capability, required_input_modality=input_modality, required_output_modality=output_modality)
    command.add_argument("--provider", default="google")
    command.add_argument("--model", required=True)
    command.add_argument("--catalog", type=Path, default=Path("ai-catalog.yaml"))
    command.add_argument("--discovered", type=Path, default=Path("ai-discovered.yaml"))
    command.add_argument("--no-refresh", action="store_true")
    command.add_argument("--max-age-hours", type=float, default=24.0)
    command.add_argument("--sensitivity-tier", choices=("normal", "sensitive"), default="normal",
                         help="workload sensitivity; sensitive e-INFRA models must be verified on-premise")


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
    if args.command == "policy-check":
        from .policies import model_policy_reason, route_policy_decision

        access_method = "browser" if args.route == "browser-chat" else "provider-cli" if args.route == "cli-chat" else "openai-compatible"
        decision = route_policy_decision(access_method, args.sensitivity_tier)
        model_reason = model_policy_reason(args.provider, args.model, args.sensitivity_tier, args.catalog)
        allowed = decision.allowed and model_reason is None
        print(json.dumps({
            "allowed": allowed,
            "reason": model_reason or decision.reason,
            "route": args.route,
            "provider": args.provider,
            "model": args.model,
            "sensitivity_tier": args.sensitivity_tier,
        }))
        return 0 if allowed else 1
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
    if args.command == "catalog-health":
        from .provider_health import check_recorded_failures, format_health
        print(format_health(check_recorded_failures(args.data_root, args.catalog, args.discovered)))
        return 0
    if args.command == "credentials":
        from .credentials import CredentialReference, KeyringCredentialStore
        store = KeyringCredentialStore()
        if args.credential_command == "set":
            if args.from_env:
                env_name = {
                    "openai": "OPENAI_API_KEY",
                    "einfra": "CERIT_API_KEY",
                    "anthropic": "ANTHROPIC_API_KEY",
                    "google": "GOOGLE_API_KEY",
                }.get(args.provider)
                if env_name is None:
                    raise SystemExit(f"unsupported provider: {args.provider}")
                value = os.environ.get(env_name)
                if not value:
                    raise SystemExit(f"missing environment variable: {env_name}")
            else:
                value = getpass.getpass(f"{args.provider} API key: ")
            store.create(args.provider, value, args.provider)
            print(f"stored credential: {args.provider}")
        elif args.credential_command == "remove":
            store.delete(CredentialReference(args.provider, args.provider, "keyring", args.provider, args.provider))
            print(f"removed credential: {args.provider}")
        else:
            print("supported credential names: openai, einfra, anthropic, google")
        return 0
    if args.command == "catalog-options":
        from .model_options import load_model_options, refresh_if_stale
        if not args.no_refresh:
            refresh_if_stale(args.catalog, args.discovered, max_age_hours=args.max_age_hours)
        options = load_model_options(args.catalog, args.discovered)
        if args.provider:
            options = [option for option in options if option["provider_id"] == args.provider]
        if args.capability:
            options = [option for option in options if args.capability in option.get("capabilities", [])]
        print(json.dumps(options, indent=2, default=str) if args.json else _format_options(options))
        return 0
    if args.command == "ai-chat":
        return run_unified_chat(args)
    if args.command == "ai-embed":
        return run_embedding(args)
    if args.command == "ai-image":
        return run_image_generation(args)
    if args.command == "ai-speech":
        return run_speech(args)
    if args.command == "ai-image-analyze":
        return run_image_analysis(args)
    if args.command == "ai-transcribe":
        return run_transcription(args)
    if args.command == "browser-chat":
        if args.manual:
            from .manual_browser_chat import run_manual_browser_chat
            return run_manual_browser_chat(args)
        from .browser_chat import run_browser_chat
        return run_browser_chat(args)
    if args.command == "cli-chat":
        if args.provider and args.agent and args.provider != args.agent:
            raise SystemExit("provider and --agent must identify the same CLI")
        args.provider = args.provider or args.agent
        if args.provider is None:
            raise SystemExit("cli-chat requires a provider or --agent")
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


def _format_options(options: list[dict[str, object]]) -> str:
    lines = ["provider  model                         input       output      route              status"]
    lines.append("-" * 92)
    for option in options:
        inputs = ",".join(str(value) for value in option.get("input_modalities", [])) or "unknown"
        outputs = ",".join(str(value) for value in option.get("output_modalities", [])) or "unknown"
        lines.append(f"{option['provider_id']!s:9} {str(option['model_id'])[:29]:29} {inputs[:11]:11} {outputs[:11]:11} {option['access_method']!s:18} {option['status']}")
    return "\n".join(lines)


def _run_unified_chat(args: argparse.Namespace) -> int:
    from .model_options import load_model_options, refresh_if_stale, select_model

    if not args.no_refresh:
        refresh_if_stale(args.catalog, args.discovered, max_age_hours=args.max_age_hours)
    option = select_model(
        load_model_options(args.catalog, args.discovered), args.provider, args.model, args.route,
        required_capability="chat",
        sensitivity_tier=getattr(args, "sensitivity_tier", "normal"),
    )
    adapter_type = option["adapter_type"]
    if adapter_type == "openai-api":
        return run_gpt_chat(argparse.Namespace(
            data_root=args.data_root, prompt=args.prompt, model=args.model,
            api_key_env=option["credential_env"] or "OPENAI_API_KEY", base_url="https://api.openai.com/v1", title=args.title,
            profile=getattr(args, "profile", None), pipeline_id=getattr(args, "pipeline_id", None),
            stage_index=getattr(args, "stage_index", None),
        ))
    if adapter_type in {"anthropic-api", "gemini-api"}:
        from .anthropic_api import normalize_response as normalize_anthropic_response
        from .gemini_api import normalize_response as normalize_gemini_response
        from .native_chat import run_native_chat
        provider = option["provider_id"]
        return run_native_chat(
            argparse.Namespace(
                data_root=args.data_root, prompt=args.prompt, model=args.model,
                api_key_env=option["credential_env"], title=args.title,
                profile=getattr(args, "profile", None), pipeline_id=getattr(args, "pipeline_id", None),
                stage_index=getattr(args, "stage_index", None),
            ),
            provider=provider,
            adapter_type=adapter_type,
            base_url=option["endpoint"],
            normalize=normalize_anthropic_response if provider == "anthropic" else normalize_gemini_response,
        )
    if adapter_type == "openai-compatible":
        if option["provider_id"] == "einfra":
            return run_cerit_chat(argparse.Namespace(
                data_root=args.data_root, prompt=args.prompt, model=args.model,
                api_key_env=option["credential_env"] or "CERIT_API_KEY", base_url="https://llm.ai.e-infra.cz/v1",
                title=args.title, thinking=getattr(args, "thinking", None),
                sensitivity_tier=getattr(args, "sensitivity_tier", "normal"),
                profile=getattr(args, "profile", None), pipeline_id=getattr(args, "pipeline_id", None),
                stage_index=getattr(args, "stage_index", None), catalog=args.catalog,
            ))
        return run_chat(argparse.Namespace(
            data_root=args.data_root, prompt=args.prompt, model=args.model,
            base_url=option["endpoint"], title=args.title,
            profile=getattr(args, "profile", None), pipeline_id=getattr(args, "pipeline_id", None),
            stage_index=getattr(args, "stage_index", None),
        ))
    if adapter_type == "provider-cli":
        from .cli_chat import run_cli_chat
        executable = {"openai": "codex", "anthropic": "claude", "google": "agy"}.get(str(option["provider_id"]))
        if executable is None:
            raise SystemExit(
                f"provider {option['provider_id']!r} has no configured CLI executable; use an API route or configure a provider-specific CLI"
            )
        return run_cli_chat(argparse.Namespace(
            data_root=args.data_root, prompt=args.prompt, provider=executable,
            title=args.title, allow_unknown_connectivity=True,
            profile=getattr(args, "profile", None), pipeline_id=getattr(args, "pipeline_id", None),
            stage_index=getattr(args, "stage_index", None), sensitivity_tier=getattr(args, "sensitivity_tier", "normal"),
            writable=False, credential_provider=None, model=None, mcp_server=None, catalog=args.catalog,
            workspace=None, agent=None,
        ))
    raise SystemExit(f"unsupported unified route: {adapter_type}")


def run_unified_chat(args: argparse.Namespace) -> int:
    try:
        return _run_unified_chat(args)
    except (ConnectionError, OSError, RuntimeError, TimeoutError) as exc:
        from .model_options import load_model_options, select_model
        from .provider_health import format_health, record_failure

        try:
            option = select_model(
                load_model_options(args.catalog, args.discovered), args.provider, args.model, args.route,
                required_capability="chat",
            )
            record = record_failure(
                args.data_root, args.catalog, args.discovered,
                provider_id=str(option["provider_id"]), model_id=args.model,
                route=str(option["access_method"]), error=str(exc),
            )
            print(f"provider health: {format_health([record])}", file=sys.stderr)
        except (ConnectionError, OSError, RuntimeError, TimeoutError, ValueError, KeyError, TypeError) as health_error:
            print(f"provider health check failed: {health_error}", file=sys.stderr)
        raise


def _execute_multimodal_task(args: argparse.Namespace, option: dict[str, object], credential: str | None,
                             operation: str, input_summary: str, adapter_options: dict[str, object]):
    from .multimodal_adapter import MultimodalAdapter

    sessions = SessionService(args.data_root)
    session = sessions.create(f"{args.provider} {operation}: {args.model}")
    configuration = AIConfiguration(
        name=f"{args.provider}: {args.model}", provider_id=args.provider,
        model_reference=args.model, access_method_id=str(option["access_method"]),
        location="local" if args.provider == "ollama" else "provider-cloud",
        network="localhost" if args.provider == "ollama" else "public-internet",
        adapter_options={"provider_id": args.provider, "endpoint": str(option["endpoint"]),
                         "operation": operation, "pricing": option.get("pricing", {}), **adapter_options},
        declared_capabilities=[str(args.required_capability)],
    )
    interaction = sessions.append_interaction(session, configuration.id, 1)
    request = AIRequest(
        session_id=session.id, interaction_id=interaction.id, configuration_id=configuration.id,
        messages=[{"role": "user", "content": input_summary}],
        execution_options={"operation": operation},
    )
    manager = ExecutionManager(args.data_root)
    execution = manager.prepare(request, configuration, session)
    try:
        execution, response = manager.execute(
            execution, request, configuration, MultimodalAdapter(), credential=credential,
        )
    except (ConnectionError, OSError, RuntimeError, TimeoutError) as exc:
        from .provider_health import format_health, record_failure

        try:
            health_record = record_failure(
                args.data_root, args.catalog, args.discovered,
                provider_id=str(option["provider_id"]), model_id=args.model,
                route=str(option["access_method"]), error=str(exc),
            )
            print(f"provider health: {format_health([health_record])}", file=sys.stderr)
        except (ConnectionError, OSError, RuntimeError, TimeoutError, ValueError, KeyError, TypeError) as health_error:
            print(f"provider health check failed: {health_error}", file=sys.stderr)
        raise
    return sessions, session, interaction, execution, response


def _record_multimodal_result(sessions: SessionService, session, interaction, execution, operation: str,
                              content: str, metadata: dict[str, object] | None = None) -> str:
    result = IntermediateResult(
        session_id=session.id, interaction_id=interaction.id, execution_id=execution.id,
        sequence_number=1, result_type=operation, metadata=metadata or {},
    )
    sessions.add_result(result, content)
    session.active_result_id = result.id
    return session.id


def _select_capability_task(args: argparse.Namespace) -> tuple[dict[str, object], str]:
    from .credentials import resolve_provider_credential
    from .model_options import load_model_options, refresh_if_stale, select_model

    if not args.no_refresh:
        refresh_if_stale(args.catalog, args.discovered, max_age_hours=args.max_age_hours)
    try:
        option = select_model(
            load_model_options(args.catalog, args.discovered), args.provider, args.model, "auto",
            required_capability=args.required_capability,
            required_input_modality=args.required_input_modality,
            required_output_modality=args.required_output_modality,
            sensitivity_tier=getattr(args, "sensitivity_tier", "normal"),
        )
    except ValueError as exc:
        # Model-selection failures are expected user errors (for example, asking
        # a text-only model to inspect an image), not programming failures. Keep
        # the CLI concise and actionable instead of exposing a traceback.
        raise SystemExit(f"cannot use {args.provider}/{args.model}: {exc}") from exc
    compatible = option["adapter_type"] in {"openai-api", "openai-compatible", "gemini-api"}
    if not compatible:
        raise SystemExit("selected route does not support this non-text task")
    credential = resolve_provider_credential(args.provider, option["credential_env"])
    if not credential and getattr(args, "require_credential", True) and args.provider != "ollama":
        raise SystemExit(f"missing {args.provider} API key; store it with credentials set or provide the environment variable")
    return option, credential


def run_embedding(args: argparse.Namespace) -> int:
    import json

    if not args.input.is_file():
        raise SystemExit(f"input text file not found: {args.input}")
    option, credential = _select_capability_task(args)
    sessions, session, interaction, execution, response = _execute_multimodal_task(
        args, option, credential, "embedding", f"text file: {args.input}", {"input_path": str(args.input)},
    )
    vector = response.value
    usage = response.journal_payload.get("usage", {})
    serialized = json.dumps({"model": args.model, "dimensions": len(vector), "values": vector}, indent=2)
    session_id = _record_multimodal_result(
        sessions, session, interaction, execution, "embedding",
        f"embedding with {len(vector)} dimensions", {"dimensions": len(vector), "usage": usage},
    )
    if args.output:
        args.output.write_text(serialized + "\n", encoding="utf-8")
        print(f"embedding written: {args.output} ({len(vector)} dimensions)")
    else:
        print(serialized)
    print(f"session: {session_id}")
    return 0


def run_image_generation(args: argparse.Namespace) -> int:
    option, credential = _select_capability_task(args)
    sessions, session, interaction, execution, response = _execute_multimodal_task(
        args, option, credential, "image-generation", args.prompt, {"prompt": args.prompt},
    )
    data, mime = response.value, response.journal_payload["mime_type"]
    args.output.write_bytes(data)
    session_id = _record_multimodal_result(
        sessions, session, interaction, execution, "image-generation",
        f"image written to {args.output}", {"mime_type": mime, "output": str(args.output), "bytes": len(data)},
    )
    print(f"image written: {args.output} ({mime})")
    print(f"session: {session_id}")
    return 0


def run_speech(args: argparse.Namespace) -> int:
    option, credential = _select_capability_task(args)
    sessions, session, interaction, execution, response = _execute_multimodal_task(
        args, option, credential, "speech-synthesis", args.text, {"prompt": args.text},
    )
    data, mime = response.value, response.journal_payload["mime_type"]
    args.output.write_bytes(data)
    session_id = _record_multimodal_result(
        sessions, session, interaction, execution, "speech-synthesis",
        f"audio written to {args.output}", {"mime_type": mime, "output": str(args.output), "bytes": len(data)},
    )
    print(f"speech written: {args.output} ({mime})")
    print(f"session: {session_id}")
    return 0


def run_image_analysis(args: argparse.Namespace) -> int:
    if not args.input.is_file():
        raise SystemExit(f"input image file not found: {args.input}")
    option, credential = _select_capability_task(args)
    sessions, session, interaction, execution, response = _execute_multimodal_task(
        args, option, credential, "image-analysis", f"image: {args.input}; prompt: {args.prompt}",
        {"input_path": str(args.input), "prompt": args.prompt},
    )
    result = str(response.value)
    session_id = _record_multimodal_result(sessions, session, interaction, execution, "image-analysis", result, response.journal_payload)
    print(result)
    print(f"session: {session_id}")
    return 0


def run_transcription(args: argparse.Namespace) -> int:
    if not args.input.is_file():
        raise SystemExit(f"input audio file not found: {args.input}")
    option, credential = _select_capability_task(args)
    sessions, session, interaction, execution, response = _execute_multimodal_task(
        args, option, credential, "transcription", f"audio: {args.input}", {"input_path": str(args.input)},
    )
    result = str(response.value)
    session_id = _record_multimodal_result(sessions, session, interaction, execution, "transcription", result, response.journal_payload)
    print(result)
    print(f"session: {session_id}")
    return 0


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
            profile=getattr(args, "profile", None), pipeline_id=getattr(args, "pipeline_id", None),
            stage_index=getattr(args, "stage_index", None),
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
    from .credentials import resolve_provider_credential
    _enforce_einfra_model_sensitivity(
        args.model, getattr(args, "sensitivity_tier", "normal"), getattr(args, "catalog", Path("ai-catalog.yaml")),
    )
    credential = resolve_provider_credential("einfra", args.api_key_env)
    if not credential:
        raise SystemExit(f"missing CERIT API key; set ${args.api_key_env} without putting it in configuration files")
    root = args.data_root
    sessions = SessionService(root)
    session = sessions.create(args.title)
    configuration = AIConfiguration(
        name=f"CERIT: {args.model}", provider_id="einfra", access_method_id="openai-compatible",
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
        thinking = getattr(args, "thinking", None)
        generation_options = {} if thinking is None else {"thinking": thinking}
        request = AIRequest(
            session_id=session.id, interaction_id=interaction.id, configuration_id=configuration.id,
            messages=list(messages), generation_options=generation_options,
            execution_options={"sensitivity_tier": getattr(args, "sensitivity_tier", "normal")},
            profile=getattr(args, "profile", None), pipeline_id=getattr(args, "pipeline_id", None),
            stage_index=getattr(args, "stage_index", None),
        )
        execution = manager.prepare(request, configuration, session)
        execution, response = manager.execute(execution, request, configuration, adapter, credential=credential)
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


def _enforce_einfra_model_sensitivity(model: str, sensitivity_tier: str, catalog: Path) -> None:
    if sensitivity_tier == "normal":
        return
    from .model_options import load_model_options, select_model

    try:
        select_model(
            load_model_options(catalog, Path(".most-no-discovery.yaml")),
            "einfra", model, sensitivity_tier=sensitivity_tier,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


def run_gpt_chat(args: argparse.Namespace, *, registry=None) -> int:
    """Run a journaled OpenAI Responses API chat using an environment key."""
    from .credentials import resolve_provider_credential
    from .openai_api import normalize_response as normalize_openai_response
    credential = resolve_provider_credential("openai", args.api_key_env)
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
        request = AIRequest(
            session_id=session.id, interaction_id=interaction.id, configuration_id=configuration.id,
            messages=list(messages), profile=getattr(args, "profile", None),
            pipeline_id=getattr(args, "pipeline_id", None), stage_index=getattr(args, "stage_index", None),
        )
        execution = manager.prepare(request, configuration, session)
        execution, response = manager.execute(execution, request, configuration, adapter, credential=credential)
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
