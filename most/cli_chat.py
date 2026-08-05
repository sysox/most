"""Journaled communication through installed provider CLI clients."""

from __future__ import annotations

import json
import tempfile
from argparse import Namespace
from pathlib import Path

from .adapters import Connectivity, Observability
from .cli_adapter import CLIAdapter
from .credentials import resolve_provider_credential
from .models import AIConfiguration, AIRequest, IntermediateResult, new_id
from .journal import validate_operation_id
from .services import ConfigurationService, ExecutionManager, SessionService

CLI_EXECUTABLES = {
    "codex": "codex",
    "claude": "claude",
    "gemini": "gemini",
    "agy": "agy",
    "opencode": "opencode",
}

MCP_SERVERS = {
    "ddg_search": "https://llm.ai.e-infra.cz/ddg_search/mcp",
    "DocFork": "https://llm.ai.e-infra.cz/DocFork/mcp",
    "npmjs": "https://llm.ai.e-infra.cz/npmjs/mcp",
    "solver": "https://llm.ai.e-infra.cz/solver/mcp",
    "prolog": "https://llm.ai.e-infra.cz/prolog/mcp",
    "k8scerit": "https://llm.ai.e-infra.cz/k8scerit/mcp",
    "shadcn": "https://llm.ai.e-infra.cz/shadcn/mcp",
    "tailwind": "https://llm.ai.e-infra.cz/tailwind/mcp",
}


def validate_cli_workspace_path(workspace: Path, data_root: Path) -> Path:
    """Reject workspaces that could expose MOST's own data directory."""
    candidate = workspace.resolve()
    forbidden = data_root.resolve()
    if candidate == forbidden or candidate in forbidden.parents or forbidden in candidate.parents:
        raise ValueError("workspace overlaps MOST data-root")
    return candidate


def command_for(provider: str, prompt: str, *, writable: bool = False) -> tuple[str, ...]:
    if provider == "codex":
        if writable:
            return ("exec", "--sandbox", "workspace-write", "--skip-git-repo-check", prompt)
        return ("exec", "--ephemeral", "--sandbox", "read-only", "--skip-git-repo-check", prompt)
    if provider == "claude":
        if writable:
            return ("-p", "--permission-mode", "acceptEdits", prompt)
        return ("-p", prompt)
    if writable:
        raise ValueError(f"writable mode is not implemented for {provider}")
    if provider == "gemini":
        return ("-p", prompt)
    if provider == "agy":
        return ("--output-format", "text", "--sandbox", "--print", prompt)
    if provider == "opencode":
        return ("run", prompt)
    raise ValueError(f"unsupported CLI provider: {provider}")


def credential_environment(cli: str, provider: str, model: str | None) -> tuple[dict[str, str], str]:
    """Return non-secret child environment settings for a provider-routed CLI."""
    if provider != "einfra":
        raise ValueError(f"unsupported CLI credential provider: {provider}")
    if cli == "claude":
        environment = {
            "ANTHROPIC_BASE_URL": "https://llm.ai.e-infra.cz/",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        }
        if model:
            environment["ANTHROPIC_MODEL"] = model
        return environment, "ANTHROPIC_AUTH_TOKEN"
    if cli == "codex":
        environment = {"OPENAI_BASE_URL": "https://llm.ai.e-infra.cz"}
        return environment, "OPENAI_API_KEY"
    if cli == "opencode":
        environment = {"OPENAI_BASE_URL": "https://llm.ai.e-infra.cz/v1"}
        return environment, "OPENAI_API_KEY"
    raise ValueError(f"e-INFRA credentials are not implemented for {cli}")


def mcp_config_payload(server_names: list[str], operation_id: str | None = None) -> dict[str, object]:
    unknown = sorted(set(server_names) - MCP_SERVERS.keys())
    if unknown:
        raise ValueError(f"unknown e-INFRA MCP server(s): {', '.join(unknown)}")
    payload = {
        "mcpServers": {
            name: {
                "type": "http",
                "url": MCP_SERVERS[name],
                "headers": {"Authorization": "Bearer ${MOST_MCP_AUTH}"},
            }
            for name in dict.fromkeys(server_names)
        }
    }
    if operation_id:
        for server in payload["mcpServers"].values():
            server["headers"]["X-Tandem-Operation-Id"] = "${MOST_TANDEM_OPERATION_ID}"
    return payload


def opencode_config_payload(model: str | None, server_names: list[str], operation_id: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "$schema": "https://opencode.ai/config.json",
        "provider": {
            "einfra": {
                "npm": "@ai-sdk/openai-compatible",
                "name": "e-INFRA",
                "options": {
                    "baseURL": "https://llm.ai.e-infra.cz/v1",
                    "apiKey": "{env:OPENAI_API_KEY}",
                },
                "models": {model: {"name": model}} if model else {},
            }
        },
    }
    if model:
        payload["model"] = f"einfra/{model}"
    if server_names:
        payload["mcp"] = {
            name: {
                "type": "remote",
                "url": MCP_SERVERS[name],
                "enabled": True,
                "oauth": False,
                "headers": {"Authorization": "Bearer {env:MOST_MCP_AUTH}"},
            }
            for name in dict.fromkeys(server_names)
        }
        if operation_id:
            for server in payload["mcp"].values():
                server["headers"]["X-Tandem-Operation-Id"] = "{env:MOST_TANDEM_OPERATION_ID}"
    return payload


class ProviderCLIAdapter:
    adapter_type = "provider-cli"

    def __init__(self, provider: str, working_directory: Path, *, writable: bool = False):
        self.provider = provider
        self.working_directory = working_directory
        self.writable = writable
        self.cli = CLIAdapter()

    def validate_configuration(self, configuration):
        return self.cli.validate_configuration(configuration)

    def resolve_connectivity(self, configuration):
        return Connectivity(None, "unknown", "unknown", "UNKNOWN", ("provider CLI route is opaque",))

    def get_observability_profile(self, configuration):
        return Observability.TEXT_STREAM

    def execute(self, request, configuration, credential=None):
        messages = request.get("messages", [])
        prompt = _transcript_prompt(messages)
        arguments = list(command_for(self.provider, prompt, writable=self.writable))
        runtime_configuration = {
            **configuration,
            "adapter_options": {**configuration.get("adapter_options", {}), "arguments": arguments},
        }
        operation_id = request.get("operation_id")
        if operation_id:
            environment = dict(runtime_configuration["adapter_options"].get("environment", {}))
            environment["MOST_TANDEM_OPERATION_ID"] = str(operation_id)
            runtime_configuration["adapter_options"]["environment"] = environment
        mcp_path = None
        mcp_servers = configuration.get("adapter_options", {}).get("mcp_servers", [])
        opencode_model = configuration.get("adapter_options", {}).get("opencode_model")
        if self.provider == "opencode" and opencode_model:
            environment = dict(runtime_configuration["adapter_options"].get("environment", {}))
            environment["OPENCODE_CONFIG_CONTENT"] = json.dumps(
                opencode_config_payload(str(opencode_model), list(mcp_servers), str(operation_id) if operation_id else None)
            )
            runtime_configuration["adapter_options"]["environment"] = environment
        if mcp_servers:
            if self.provider == "claude":
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", suffix=".json", prefix=".most-mcp-",
                    dir=self.working_directory, delete=False,
                ) as handle:
                    mcp_path = Path(handle.name)
                    json.dump(mcp_config_payload(list(mcp_servers), str(operation_id) if operation_id else None), handle)
                runtime_configuration["adapter_options"]["arguments"] = [*arguments, "--mcp-config", str(mcp_path)]
            elif self.provider != "opencode":
                raise ValueError("MCP is currently supported only for Claude and OpenCode CLI")
        try:
            result = self.cli.execute(request, runtime_configuration, credential)
        finally:
            if mcp_path is not None:
                mcp_path.unlink(missing_ok=True)
        stdout, stderr, returncode = result["stdout"], result["stderr"], result["returncode"]
        if returncode != 0:
            raise RuntimeError(f"{self.provider} CLI exited with status {returncode}: {stderr or stdout}")
        content = stdout.strip()
        if not content:
            detail = stderr.strip() or "no output"
            raise RuntimeError(f"{self.provider} CLI returned no assistant output: {detail}")
        return {"content": content, "stderr": stderr, "returncode": returncode}


def rewind_messages(messages: list[dict[str, str]], turns: int = 1) -> int:
    """Remove complete user/assistant exchanges from the active context."""
    if turns < 1:
        raise ValueError("rewind turns must be a positive integer")
    exchange_count = len(messages) // 2
    if turns > exchange_count:
        raise ValueError(f"cannot rewind {turns} turn(s); only {exchange_count} available")
    del messages[-(turns * 2):]
    return turns


def run_cli_chat(args: Namespace) -> int:
    writable = bool(getattr(args, "writable", False))
    credential_provider = getattr(args, "credential_provider", None)
    model = getattr(args, "model", None)
    if credential_provider == "einfra":
        _enforce_einfra_model_sensitivity(
            model, getattr(args, "sensitivity_tier", "normal"), getattr(args, "catalog", Path("ai-catalog.yaml")),
        )
    credential = None
    environment: dict[str, str] = {}
    credential_env_var = None
    mcp_servers = list(getattr(args, "mcp_server", []) or [])
    no_mcp = bool(getattr(args, "no_mcp", False))
    operation_id = getattr(args, "operation_id", None)
    if operation_id:
        try:
            operation_id = validate_operation_id(operation_id)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        environment["MOST_TANDEM_OPERATION_ID"] = operation_id
    if no_mcp and mcp_servers:
        raise SystemExit("--no-mcp cannot be combined with --mcp-server")
    if credential_provider:
        if args.provider not in {"codex", "claude", "opencode"}:
            raise SystemExit("--credential-provider einfra currently supports only codex and claude")
        environment, credential_env_var = credential_environment(args.provider, credential_provider, model)
        credential = resolve_provider_credential(credential_provider)
        if not credential:
            raise SystemExit("missing einfra credential; run `most credentials set einfra` first")
        if args.provider == "claude" and not no_mcp:
            mcp_servers = list(dict.fromkeys(["ddg_search", *mcp_servers]))
    elif mcp_servers:
        raise SystemExit("--mcp-server requires --credential-provider einfra")
    selected_workspace = getattr(args, "workspace", None)
    if selected_workspace is not None:
        try:
            sandbox = validate_cli_workspace_path(Path(selected_workspace), args.data_root)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        if not sandbox.is_dir():
            raise SystemExit(f"workspace directory not found: {sandbox}")
        if not writable:
            raise SystemExit("--workspace requires --writable so file access is explicit")
    else:
        sandbox = (args.data_root / "cli-sandboxes" / args.provider).resolve()
        sandbox.mkdir(parents=True, exist_ok=True)
    sessions = SessionService(args.data_root)
    session = sessions.create(args.title)
    configuration = AIConfiguration(
        name=f"CLI: {args.provider}",
        provider_id=args.provider,
        access_method_id="provider-cli",
        location="provider-cloud",
        network="unknown",
        adapter_options={
            "executable": CLI_EXECUTABLES[args.provider],
            "working_directory": str(sandbox),
            "arguments": list(command_for(args.provider, "<prompt>", writable=writable)),
            "environment": environment,
            "credential_env_var": credential_env_var,
            "credential_env_vars": [value for value in (credential_env_var, "MOST_MCP_AUTH") if value],
            "mcp_servers": mcp_servers,
            "opencode_model": model,
        },
    )
    ConfigurationService(args.data_root).save(configuration)
    manager = ExecutionManager(args.data_root)
    adapter = ProviderCLIAdapter(args.provider, sandbox, writable=writable)
    messages: list[dict[str, str]] = []
    prompt = args.prompt
    while True:
        if prompt is None:
            prompt = input("you> ")
        prompt = prompt.strip()
        if prompt.lower() in {"/exit", "/quit"}:
            break
        if prompt.lower().startswith("/rewind"):
            parts = prompt.split()
            try:
                turns = int(parts[1]) if len(parts) == 2 else 1
                removed = rewind_messages(messages, turns)
            except (ValueError, IndexError) as exc:
                print(f"rewind> {exc}")
            else:
                sessions.journal.record_event(session.id, {
                    "event_type": "conversation_rewind",
                    "rewind_id": new_id(),
                    "removed_turns": removed,
                    "remaining_messages": len(messages),
                })
                print(f"rewind> removed {removed} turn(s); {len(messages)} messages remain in context")
            if args.prompt is not None:
                break
            prompt = None
            continue
        messages.append({"role": "user", "content": prompt})
        checkpoint_id = new_id()
        sessions.journal.record_event(session.id, {
            "event_type": "conversation_checkpoint",
            "checkpoint_id": checkpoint_id,
            "turn_number": (len(messages) + 1) // 2,
            "message_count": len(messages),
        })
        interaction = sessions.append_interaction(session, configuration.id, len(messages))
        request = AIRequest(
            session_id=session.id,
            interaction_id=interaction.id,
            configuration_id=configuration.id,
            messages=list(messages),
            execution_options={"sensitivity_tier": getattr(args, "sensitivity_tier", "normal")},
            profile=getattr(args, "profile", None),
            pipeline_id=getattr(args, "pipeline_id", None),
            stage_index=getattr(args, "stage_index", None),
            operation_id=getattr(args, "operation_id", None),
        )
        execution = manager.prepare(request, configuration, session)
        execution, response = manager.execute(
            execution,
            request,
            configuration,
            adapter,
            credential=credential,
            confirmation=args.allow_unknown_connectivity,
        )
        content = str(response["content"])
        result = IntermediateResult(
            session_id=session.id,
            interaction_id=interaction.id,
            execution_id=execution.id,
            sequence_number=len(messages),
            result_type="response",
            parent_result_id=session.active_result_id,
            profile=getattr(args, "profile", None),
            pipeline_id=getattr(args, "pipeline_id", None),
            stage_index=getattr(args, "stage_index", None),
            operation_id=getattr(args, "operation_id", None),
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


def _enforce_einfra_model_sensitivity(model: str | None, sensitivity_tier: str, catalog: Path) -> None:
    if sensitivity_tier == "normal":
        return
    if not model:
        raise SystemExit("--model is required for sensitive e-INFRA CLI sessions")
    try:
        from .policies import model_policy_reason
        reason = model_policy_reason("einfra", model, sensitivity_tier, catalog)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot evaluate e-INFRA model policy: {exc}") from exc
    if reason:
        raise SystemExit(reason)


def _transcript_prompt(messages: list[dict[str, object]]) -> str:
    lines = ["You are continuing a terminal conversation. Reply to the final user message."]
    for message in messages:
        lines.append(f"{message.get('role', 'user')}: {message.get('content', '')}")
    return "\n".join(lines)
