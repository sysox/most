"""Browser profile isolation and conservative browser adapter boundary."""

from __future__ import annotations

from pathlib import Path

from .adapters import Connectivity, Observability


class BrowserProfileIsolationError(ValueError):
    pass


class IsolatedBrowserProfileService:
    def __init__(self, managed_root: Path):
        self.managed_root = managed_root.resolve()
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

    def __init__(self, profile_service: IsolatedBrowserProfileService):
        self.profile_service = profile_service

    def get_observability_profile(self, configuration: dict[str, object]) -> Observability:
        return Observability.BLOCK

    def validate_configuration(self, configuration: dict[str, object]) -> list[str]:
        profile = configuration.get("profile_path")
        if not isinstance(profile, str):
            return ["profile_path is required"]
        try:
            self.profile_service.validate_isolated_profile_path(Path(profile), [])
        except BrowserProfileIsolationError as exc:
            return [str(exc)]
        return []

    def resolve_connectivity(self, configuration: dict[str, object]) -> Connectivity:
        return Connectivity(None, "browser-session", "public-internet", "DECLARED", ("browser provider route is opaque",))

    def execute(self, configuration: dict[str, object]) -> None:
        raise RuntimeError("browser execution requires a provider-specific selector pack")
