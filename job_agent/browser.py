from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright


class BrowserSession:
    """A persistent Playwright session.

    The browser is visible by default so the user can log in or solve a
    CAPTCHA. The agent never bypasses either; it pauses and asks the user.
    """

    def __init__(self, user_data_dir: Path, headless: bool = False):
        self.user_data_dir = Path(user_data_dir)
        self.headless = headless
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._browser: Browser | None = None
        self.page: Page | None = None

    def start(self) -> Page:
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = sync_playwright().start()
        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.user_data_dir),
            headless=self.headless,
        )
        if self._context.pages:
            self.page = self._context.pages[0]
        else:
            self.page = self._context.new_page()
        return self.page

    def screenshot(self, path: Path) -> Path:
        if self.page is None:
            raise RuntimeError("browser session is not started")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(path), full_page=True)
        return path

    def pause_for_login(self, message: str) -> None:
        if self.page is None:
            raise RuntimeError("browser session is not started")
        print(message)
        self.screenshot(self.user_data_dir / "login.png")
        input("Press Enter after you have finished logging in / solving the CAPTCHA...")

    def close(self) -> None:
        if self._context is not None:
            self._context.close()
            self._context = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None
        self.page = None
