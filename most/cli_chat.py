"""Journaled communication through installed provider CLI clients."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from .adapters import Connectivity, Observability
from .cli_adapter import CLIAdapter
from .models import AIConfiguration, AIRequest, IntermediateResult
from .services import ConfigurationService, ExecutionManager, SessionService

CLI_EXECUTABLES = {
    "codex": "codex",
    "claude": "claude",
    "gemini": "gemini",
    "agy": "agy",
}


def command_for(provider: str, prompt: str) -> tuple[str, ...]:
    if provider == "codex":
        return ("exec", "--ephemeral", "--sandbox", "read-only", "--skip-git-repo-check", prompt)
    if provider == "claude":
        return ("-p", prompt)
    if provider == "gemini":
        return ("-p", prompt)
    if provider == "agy":
        return ("--print", "--output-format", "text", "--sandbox", prompt)
    raise ValueError(f"unsupported CLI provider: {provider}")


class ProviderCLIAdapter:
    adapter_type = "provider-cli"

    def __init__(self, provider: str, working_directory: Path):
        self.provider = provider
        self.working_directory = working_directory
        self.cli = CLIAdapter()

    def validate_configuration(self, configuration):
        return self.cli.validate_configuration(configuration)

    def resolve_connectivity(self, configuration):
        return Connectivity(None, "unknown", "unknown", "UNKNOWN", ("provider CLI route is opaque",))

    def get_observability_profile(self, configuration):
        return Observability.TEXT_STREAM

    def execute(self, request, configuration, credential_handle=None):
        messages = request.get("messages", [])
        prompt = _transcript_prompt(messages)
        arguments = list(command_for(self.provider, prompt))
        execution = self.cli.start(
            CLI_EXECUTABLES[self.provider],
            arguments,
            self.working_directory,
            environment=None,
        )
        stdout, stderr, returncode = self.cli.collect(execution)
        if returncode != 0:
            raise RuntimeError(f"{self.provider} CLI exited with status {returncode}: {stderr or stdout}")
        return {"content": stdout.strip(), "stderr": stderr, "returncode": returncode}


def run_cli_chat(args: Namespace) -> int:
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
            "arguments": list(command_for(args.provider, "<prompt>")),
        },
    )
    ConfigurationService(args.data_root).save(configuration)
    manager = ExecutionManager(args.data_root)
    adapter = ProviderCLIAdapter(args.provider, sandbox)
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
