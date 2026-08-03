"""Browser profile isolation and conservative browser adapter boundary."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .adapters import Connectivity, Observability


class BrowserProfileIsolationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SelectorPack:
    provider_id: str
    version: str
    selectors: dict[str, str]


@dataclass(frozen=True, slots=True)
class BrowserFailureDiagnostic:
    selector_pack_version: str
    reason: str
    screenshot_reference: str | None = None
    sanitized_dom_reference: str | None = None


class BrowserDriver(Protocol):
    def click(self, selector: str) -> None: ...
    def type_text(self, selector: str, value: str) -> None: ...
    def read_text(self, selector: str) -> str: ...
    def screenshot(self) -> str | None: ...
    def sanitized_dom(self) -> str | None: ...

    def wait_for_output(self, selector: str) -> None: ...


class IsolatedBrowserProfileService:
    def __init__(self, managed_root: Path):
        self.managed_root = Path(managed_root).resolve()
        self.managed_root.mkdir(parents=True, exist_ok=True)

    def validate_isolated_profile_path(self, profile: Path, forbidden_roots: list[Path]) -> Path:
        candidate = profile.resolve()
        if self.managed_root not in candidate.parents and candidate != self.managed_root:
            raise BrowserProfileIsolationError("browser profile must be under the managed browser-profile root")
        for forbidden in forbidden_roots:
            forbidden_path = forbidden.resolve()
            if candidate == forbidden_path or forbidden_path in candidate.parents or candidate in forbidden_path.parents:
                raise BrowserProfileIsolationError("browser profile overlaps a forbidden journal/workspace/export path")
        return candidate


class BrowserAdapter:
    adapter_type = "browser"

    def __init__(self, profile_service: IsolatedBrowserProfileService, selector_packs: dict[str, SelectorPack] | None = None):
        self.profile_service = profile_service
        self.selector_packs = selector_packs or {}

    def get_observability_profile(self, configuration: dict[str, object]) -> Observability:
        return Observability.BLOCK

    def validate_configuration(self, configuration: dict[str, object]) -> list[str]:
        profile = configuration.get("profile_path")
        if not isinstance(profile, str):
            return ["profile_path is required"]
        try:
            forbidden = [Path(str(path)) for path in configuration.get("forbidden_roots", []) if isinstance(path, str)]
            self.profile_service.validate_isolated_profile_path(Path(profile), forbidden)
        except BrowserProfileIsolationError as exc:
            return [str(exc)]
        return []

    def resolve_connectivity(self, configuration: dict[str, object]) -> Connectivity:
        return Connectivity(None, "browser-session", "public-internet", "DECLARED", ("browser provider route is opaque",))

    def execute(self, configuration: dict[str, object], driver: BrowserDriver) -> dict[str, object]:
        provider_id = str(configuration.get("provider_id", ""))
        pack = self.selector_packs.get(provider_id)
        if pack is None:
            raise RuntimeError("browser execution paused: selector pack is unavailable")
        try:
            input_selector = pack.selectors["input"]
            submit_selector = pack.selectors["submit"]
            output_selector = pack.selectors["output"]
            prompt = configuration.get("prompt")
            if not isinstance(prompt, str):
                raise TypeError("browser prompt is required")
            driver.click(input_selector)
            driver.type_text(input_selector, prompt)
            driver.click(submit_selector)
            wait_for_output = getattr(driver, "wait_for_output", None)
            if wait_for_output is not None:
                wait_for_output(output_selector)
            return {"text": driver.read_text(output_selector), "selector_pack_version": pack.version}
        except Exception as exc:
            diagnostic = BrowserFailureDiagnostic(pack.version, str(exc), driver.screenshot(), driver.sanitized_dom())
            raise RuntimeError(f"browser execution failed: {diagnostic}") from exc
