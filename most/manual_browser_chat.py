"""Manual browser relay for providers that block automated sign-in."""

from __future__ import annotations

import webbrowser
from argparse import Namespace

from .journal import JournalService
from .models import AIConfiguration, AIRequest, IntermediateResult
from .services import ConfigurationService, SessionService

URLS = {
    "chatgpt": "https://chatgpt.com/",
    "gemini": "https://gemini.google.com/app",
    "claude": "https://claude.ai/new",
    "cerit": "https://chat.ai.e-infra.cz/",
}


def run_manual_browser_chat(args: Namespace) -> int:
    """Open a normal browser and journal user-mediated prompt/response exchanges."""
    webbrowser.open(URLS[args.provider])
    sessions = SessionService(args.data_root)
    journal = JournalService(args.data_root)
    session = sessions.create(args.title)
    configuration = AIConfiguration(
        name=f"Manual browser: {args.provider}",
        provider_id=args.provider,
        access_method_id="browser-manual",
        location="browser-session",
        network="public-internet",
    )
    ConfigurationService(args.data_root).save(configuration)
    prompt = args.prompt
    messages: list[dict[str, str]] = []
    while True:
        if prompt is None:
            prompt = input("you> ")
        prompt = prompt.strip()
        if prompt.lower() in {"/exit", "/quit"}:
            break
        print("Copy this prompt into the browser, submit it there, then paste the response below.")
        print(f"prompt> {prompt}")
        messages.append({"role": "user", "content": prompt})
        interaction = sessions.append_interaction(session, configuration.id, len(messages))
        request = AIRequest(
            session_id=session.id,
            interaction_id=interaction.id,
            configuration_id=configuration.id,
            messages=list(messages),
        )
        journal.record_request(session.id, request)
        content = _read_response()
        journal.record_response(session.id, request.id, {"content": content, "provider": args.provider})
        result = IntermediateResult(
            session_id=session.id,
            interaction_id=interaction.id,
            sequence_number=len(messages),
            result_type="response",
            parent_result_id=session.active_result_id,
        )
        sessions.add_result(result, content)
        session.active_result_id = result.id
        messages.append({"role": "assistant", "content": content})
        if args.prompt is not None:
            break
        prompt = None
    print(f"session: {session.id}")
    return 0


def _read_response() -> str:
    print("response> paste response; enter /done on its own line when finished")
    lines: list[str] = []
    while True:
        line = input()
        if line == "/done":
            return "\n".join(lines).strip()
        lines.append(line)
