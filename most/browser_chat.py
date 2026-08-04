"""Journaled browser communication through a user-logged-in Firefox profile."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from .browser import BrowserAdapter, IsolatedBrowserProfileService, SelectorPack
from .browser_selenium import SeleniumFirefoxDriver
from .models import AIConfiguration, AIRequest, IntermediateResult
from .paths import managed_browser_profile_root
from .services import ExecutionManager, SessionService

SELECTOR_PACKS = {
    "chatgpt": SelectorPack("chatgpt", "2026-08", {
        "input": "#prompt-textarea",
        "submit": "button[data-testid='send-button']",
        "output": "div[data-message-author-role='assistant']",
    }),
    "gemini": SelectorPack("gemini", "2026-08", {
        "input": "rich-textarea .ql-editor",
        "submit": "button[aria-label*='Send']",
        "output": "message-content",
    }),
    "claude": SelectorPack("claude", "2026-08", {
        "input": "div[contenteditable='true']",
        "submit": "button[aria-label*='Send']",
        "output": "div[data-is-streaming='false']",
    }),
    "cerit": SelectorPack("cerit", "2026-08", {
        "input": "textarea[placeholder*='Message'], textarea",
        "submit": "button[type='submit']",
        "output": ".message-markdown, [data-message-id]",
    }),
}

URLS = {
    "chatgpt": "https://chatgpt.com/",
    "gemini": "https://gemini.google.com/app",
    "claude": "https://claude.ai/new",
    "cerit": "https://chat.ai.e-infra.cz/",
}

LOGIN_SELECTORS = {
    "gemini": "button[aria-label='Sign in']",
}


class BrowserSessionAdapter:
    adapter_type = "browser"

    def __init__(self, browser: BrowserAdapter, driver, provider: str):
        self.browser = browser
        self.driver = driver
        self.provider = provider

    def validate_configuration(self, configuration):
        return self.browser.validate_configuration(configuration["adapter_options"])

    def resolve_connectivity(self, configuration):
        return self.browser.resolve_connectivity(configuration)

    def get_observability_profile(self, configuration):
        return self.browser.get_observability_profile(configuration)

    def execute(self, request, configuration, credential=None):
        prompt = request.get("messages", [])[-1]["content"]
        browser_configuration = {
            **configuration["adapter_options"],
            "provider_id": self.provider,
            "prompt": prompt,
        }
        return self.browser.execute(browser_configuration, self.driver)


def run_browser_chat(args: Namespace) -> int:
    profile_root = managed_browser_profile_root()
    profile_name = args.profile or args.provider
    if Path(profile_name).name != profile_name or profile_name in {"", ".", ".."}:
        raise SystemExit("browser profile name must be a simple name without path separators")
    profile = profile_root / profile_name
    profile_service = IsolatedBrowserProfileService(profile_root)
    forbidden_roots = [args.data_root.resolve(), Path.cwd().resolve()]
    profile_service.validate_isolated_profile_path(profile, forbidden_roots)
    driver = SeleniumFirefoxDriver(profile, headless=args.headless)
    try:
        driver.open(URLS[args.provider])
        input_selector = SELECTOR_PACKS[args.provider].selectors["input"]
        login_selector = LOGIN_SELECTORS.get(args.provider)
        login_required = bool(login_selector and driver.wait_for_element(login_selector, timeout=5))
        if login_required or not driver.wait_for_element(input_selector, timeout=8):
            print("Log in manually if needed, then press Enter here.")
            print("Do not bypass CAPTCHA, consent, or other site safety controls.")
            input()
            if login_selector and driver.wait_for_element(login_selector, timeout=3):
                raise RuntimeError("Gemini still shows Sign in; complete login in Firefox and try again")
            if not driver.wait_for_element(input_selector, timeout=60):
                raise RuntimeError("browser login was not detected; confirm the provider page is ready and try again")
        sessions = SessionService(args.data_root)
        session = sessions.create(args.title)
        configuration = AIConfiguration(
            name=f"Browser: {args.provider}",
            provider_id=args.provider,
            access_method_id="browser",
            location="browser-session",
            network="public-internet",
            adapter_options={
                "profile_path": str(profile),
                "forbidden_roots": [str(path) for path in forbidden_roots],
            },
        )
        manager = ExecutionManager(args.data_root)
        browser = BrowserAdapter(profile_service, SELECTOR_PACKS)
        adapter = BrowserSessionAdapter(browser, driver, args.provider)
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
            execution, response = manager.execute(execution, request, configuration, adapter)
            content = str(response["text"])
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
    finally:
        driver.close()
