"""Shared journaled chat loop for native cloud APIs."""

from __future__ import annotations

from argparse import Namespace
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .adapters import create_default_registry
from .credentials import resolve_provider_credential
from .models import AIConfiguration, AIRequest, IntermediateResult
from .services import ConfigurationService, ExecutionManager, SessionService


def run_native_chat(args: Namespace, *, provider: str, adapter_type: str, base_url: str,
                    normalize: Callable[[Any], dict[str, Any]], registry=None) -> int:
    credential = resolve_provider_credential(provider, args.api_key_env)
    if not credential:
        raise SystemExit(f"missing {provider} API key; set ${args.api_key_env} or store it in the keyring")
    root = Path(args.data_root)
    sessions = SessionService(root)
    session = sessions.create(args.title)
    configuration = AIConfiguration(
        name=f"{provider}: {args.model}", provider_id=provider, access_method_id="api",
        model_reference=args.model, location="provider-cloud", network="public-internet",
        adapter_options={"base_url": base_url},
    )
    ConfigurationService(root).save(configuration)
    manager = ExecutionManager(root)
    adapter = (registry or create_default_registry()).get(adapter_type)
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
        normalized = normalize(response)
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
