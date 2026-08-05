"""Journaled communication through installed provider CLI clients."""

from __future__ import annotations

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
    raise ValueError(f"e-INFRA credentials are not implemented for {cli}")


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
        result = self.cli.execute(request, runtime_configuration, credential)
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
    credential = None
    environment: dict[str, str] = {}
    credential_env_var = None
    if credential_provider:
        if args.provider not in {"codex", "claude"}:
            raise SystemExit("--credential-provider einfra currently supports only codex and claude")
        environment, credential_env_var = credential_environment(args.provider, credential_provider, model)
        credential = resolve_provider_credential(credential_provider)
        if not credential:
            raise SystemExit("missing einfra credential; run `most credentials set einfra` first")
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


def _transcript_prompt(messages: list[dict[str, object]]) -> str:
    lines = ["You are continuing a terminal conversation. Reply to the final user message."]
    for message in messages:
        lines.append(f"{message.get('role', 'user')}: {message.get('content', '')}")
    return "\n".join(lines)
