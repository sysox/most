"""Journaled communication through installed provider CLI clients."""

from __future__ import annotations

import json
import tempfile
from argparse import Namespace
from pathlib import Path

from .adapters import Connectivity, Observability
from .cli_adapter import CLIAdapter
from .credentials import resolve_provider_credential
from .models import AIConfiguration, AIRequest, IntermediateResult
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


def command_for(provider: str, prompt: str, *, writable: bool = False) -> tuple[str, ...]:
    if provider == "codex":
        if writable:
            return ("exec", "--sandbox", "workspace-write", "--skip-git-repo-check", prompt)
        return ("exec", "--ephemeral", "--sandbox", "read-only", "--skip-git-repo-check", prompt)
    if writable:
        raise ValueError(f"writable mode is not implemented for {provider}")
    if provider == "claude":
        return ("-p", prompt)
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


def mcp_config_payload(server_names: list[str]) -> dict[str, object]:
    unknown = sorted(set(server_names) - MCP_SERVERS.keys())
    if unknown:
        raise ValueError(f"unknown e-INFRA MCP server(s): {', '.join(unknown)}")
    return {
        "mcpServers": {
            name: {
                "type": "http",
                "url": MCP_SERVERS[name],
                "headers": {"Authorization": "Bearer ${MOST_MCP_AUTH}"},
            }
            for name in dict.fromkeys(server_names)
        }
    }


def opencode_config_payload(model: str | None, server_names: list[str]) -> dict[str, object]:
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
        mcp_path = None
        mcp_servers = configuration.get("adapter_options", {}).get("mcp_servers", [])
        opencode_model = configuration.get("adapter_options", {}).get("opencode_model")
        if self.provider == "opencode" and opencode_model:
            environment = dict(runtime_configuration["adapter_options"].get("environment", {}))
            environment["OPENCODE_CONFIG_CONTENT"] = json.dumps(opencode_config_payload(str(opencode_model), list(mcp_servers)))
            runtime_configuration["adapter_options"]["environment"] = environment
        if mcp_servers:
            if self.provider == "claude":
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", suffix=".json", prefix=".most-mcp-",
                    dir=self.working_directory, delete=False,
                ) as handle:
                    mcp_path = Path(handle.name)
                    json.dump(mcp_config_payload(list(mcp_servers)), handle)
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
    if credential_provider:
        if args.provider not in {"codex", "claude", "opencode"}:
            raise SystemExit("--credential-provider einfra currently supports only codex and claude")
        environment, credential_env_var = credential_environment(args.provider, credential_provider, model)
        credential = resolve_provider_credential(credential_provider)
        if not credential:
            raise SystemExit("missing einfra credential; run `most credentials set einfra` first")
        if args.provider == "claude":
            mcp_servers = list(dict.fromkeys(["ddg_search", *mcp_servers]))
    elif mcp_servers:
        raise SystemExit("--mcp-server requires --credential-provider einfra")
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
        messages.append({"role": "user", "content": prompt})
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
    from .model_options import load_model_options, select_model

    if not model:
        raise SystemExit("--model is required for sensitive e-INFRA CLI sessions")
    try:
        select_model(
            load_model_options(catalog, Path(".most-no-discovery.yaml")),
            "einfra", model, sensitivity_tier=sensitivity_tier,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


def _transcript_prompt(messages: list[dict[str, object]]) -> str:
    lines = ["You are continuing a terminal conversation. Reply to the final user message."]
    for message in messages:
        lines.append(f"{message.get('role', 'user')}: {message.get('content', '')}")
    return "\n".join(lines)
