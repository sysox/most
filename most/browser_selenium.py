"""Optional Firefox WebDriver implementation for user-directed browser sessions."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def _firefox_binary() -> str | None:
    """Return a real Firefox executable, including Ubuntu's Snap install."""
    candidates = []
    configured = os.environ.get("MOST_FIREFOX_BINARY")
    if configured:
        candidates.append(Path(configured))
    detected = shutil.which("firefox")
    if detected:
        candidates.append(Path(detected))
    candidates.append(Path("/snap/firefox/current/usr/lib/firefox/firefox"))
    for candidate in candidates:
        if not candidate.is_file():
            continue
        if os.name != "nt" and not (candidate.stat().st_mode & 0o111):
            continue
        try:
            with candidate.open("rb") as executable:
                is_script = executable.read(2) == b"#!"
            if is_script:
                continue
        except OSError:
            continue
        return str(candidate)
    return None


class SeleniumFirefoxDriver:
    def __init__(self, profile: Path, *, headless: bool = False):
        try:
            from selenium import webdriver
            from selenium.webdriver.firefox.options import Options
            from selenium.webdriver.firefox.service import Service
        except ImportError as exc:
            raise RuntimeError("browser support requires: uv sync --extra browser") from exc
        profile = profile.resolve()
        profile.mkdir(parents=True, exist_ok=True)
        options = Options()
        binary = _firefox_binary()
        if binary:
            options.binary_location = binary
        # Let geckodriver package the profile through the WebDriver capability.
        # Passing ``-profile`` directly makes recent Snap Firefox builds reject
        # the preferences during session creation.
        options.profile = str(profile)
        if headless:
            options.add_argument("-headless")
        executable = shutil.which("geckodriver")
        service = Service(executable_path=executable) if executable else Service()
        self.driver = webdriver.Firefox(service=service, options=options)

    def open(self, url: str) -> None:
        self.driver.get(url)

    def click(self, selector: str) -> None:
        if not self.wait_for_element(selector, timeout=10) and "aria-label*='Send'" in selector:
            # Gemini periodically removes or renames its send button. The
            # editor remains focused after type_text(), and Enter is its
            # standard submit action.
            from selenium.webdriver.common.keys import Keys

            self.driver.switch_to.active_element.send_keys(Keys.ENTER)
            return
        self._element(selector).click()

    def type_text(self, selector: str, value: str) -> None:
        from selenium.webdriver.common.keys import Keys

        element = self._element(selector)
        # WebDriver's clear() uses an innerHTML setter for contenteditable
        # elements. Gemini's CSP blocks that setter, so edit through the same
        # keyboard path a user uses instead.
        element.click()
        element.send_keys(Keys.CONTROL, "a", Keys.BACKSPACE)
        element.send_keys(value)

    def read_text(self, selector: str) -> str:
        elements = self._elements(selector)
        if not elements:
            raise RuntimeError(f"browser output selector returned no elements: {selector}")
        return elements[-1].text

    def wait_for_output(self, selector: str) -> None:
        from selenium.webdriver.support.ui import WebDriverWait

        WebDriverWait(self.driver, 60).until(lambda _: any(element.text.strip() for element in self._elements(selector)))

    def wait_for_element(self, selector: str, timeout: float = 10) -> bool:
        from selenium.common.exceptions import WebDriverException
        from selenium.webdriver.support.ui import WebDriverWait

        try:
            WebDriverWait(self.driver, timeout).until(
                lambda _: any(element.is_displayed() for element in self._elements(selector))
            )
        except WebDriverException:
            return False
        return True

    def screenshot(self) -> str | None:
        return None

    def sanitized_dom(self) -> str | None:
        return None

    def close(self) -> None:
        self.driver.quit()

    def _elements(self, selector: str):
        from selenium.webdriver.common.by import By

        return self.driver.find_elements(By.CSS_SELECTOR, selector)

    def _element(self, selector: str):
        elements = self._elements(selector)
        if not elements:
            raise RuntimeError(f"browser selector returned no elements: {selector}")
        return elements[-1]
