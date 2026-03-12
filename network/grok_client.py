"""
network/grok_client.py

High-level Grok browser controller.

Responsibilities:
    - Manage browser lifecycle (start / stop / restart)
    - Restore session via SessionManager
    - Delegate login / session-persist to LoginService
    - Detect and wait for Cloudflare verification
    - Expose a ready Page to other modules

Design decisions:
    - Uses an explicit _State enum so every method can assert preconditions
      instead of silently doing nothing or crashing mysteriously.
    - Integrates LoginService from auth/ — NO duplicate login logic here.
    - Supports context-manager usage (with GrokClient() as client: …).
    - All public methods are guarded by _assert_ready() / _assert_started().
    - Browser args are centralised in one place for easy maintenance.
    - User-agent is kept up-to-date and realistic.
    - Navigation uses retry logic with exponential back-off.
    - Cloudflare detection checks multiple signals, not just page HTML.
"""

import logging
import time
from contextlib import contextmanager
from enum import Enum, auto
from typing import Callable, Iterator, Optional

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)

from auth.exceptions import BrowserNotReadyError, LoginTimeoutError
from auth.login_service import LoginSelectors, LoginService
from auth.session_manager import SessionManager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Browser lifecycle states
# ---------------------------------------------------------------------------

class _State(Enum):
    CREATED  = auto()   # __init__ done, start() not called yet
    STARTING = auto()   # inside start()
    READY    = auto()   # browser open, session restored, login confirmed
    STOPPING = auto()   # inside stop()
    STOPPED  = auto()   # fully shut down


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GROK_HOME    = "https://grok.com"
_GROK_IMAGINE = "https://grok.com/imagine"

# Selector that appears once Grok's UI has fully rendered
_UI_READY_SELECTOR = "textarea"

_CF_SIGNALS = ("cloudflare", "checking your browser", "cf-browser-verification")

_DEFAULT_VERIFICATION_TIMEOUT = 300   # seconds
_DEFAULT_NAVIGATION_TIMEOUT   = 30_000  # ms
_DEFAULT_PAGE_READY_TIMEOUT   = 20_000  # ms

_CHROME_VERSION = "124.0.0.0"

_BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
    "--no-first-run",
    "--no-default-browser-check",
    "--start-maximized",
]


# ---------------------------------------------------------------------------
# GrokClient
# ---------------------------------------------------------------------------

class GrokClient:
    """
    High-level Grok browser controller.

    Basic usage
    -----------
    >>> client = GrokClient(log_callback=print)
    >>> client.start()          # opens browser, restores session, waits for login
    >>> page = client.get_page()
    >>> client.open_imagine()
    >>> client.stop()

    Context-manager usage
    ---------------------
    >>> with GrokClient(log_callback=print) as client:
    ...     client.open_imagine()
    ...     page = client.get_page()

    Parameters
    ----------
    log_callback:
        Optional callable for human-readable status messages.
        If omitted, messages go to the stdlib logger.
    session_manager:
        Override the default SessionManager (useful for testing).
    login_selectors:
        Override the default CSS selectors used to detect login state.
    verification_timeout:
        Seconds to wait for the user to solve Cloudflare CAPTCHA.
    """

    def __init__(
        self,
        log_callback: Optional[Callable[[str], None]] = None,
        session_manager: Optional[SessionManager] = None,
        login_selectors: Optional[LoginSelectors] = None,
        verification_timeout: int = _DEFAULT_VERIFICATION_TIMEOUT,
    ) -> None:
        self._log: Callable[[str], None] = log_callback or (
            lambda msg: logger.info("[GrokClient] %s", msg)
        )
        self._session_manager  = session_manager or SessionManager()
        self._login_selectors  = login_selectors
        self._verification_timeout = verification_timeout

        # Browser objects — populated by start()
        self._playwright: Optional[Playwright]     = None
        self._browser:    Optional[Browser]        = None
        self._context:    Optional[BrowserContext] = None
        self._page:       Optional[Page]           = None

        # LoginService — created once page is available
        self._login_service: Optional[LoginService] = None

        self._state = _State.CREATED

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "GrokClient":
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """
        Launch the browser, restore the session, and ensure login.

        Raises
        ------
        RuntimeError
            If called when the client is not in CREATED state.
        LoginTimeoutError
            If the user does not log in within the allowed window.
        BrowserNotReadyError
            If the browser becomes unavailable during startup.
        """
        self._assert_state(_State.CREATED, "start()")
        self._state = _State.STARTING

        try:
            self._log("Starting GrokClient…")
            self._launch_browser()
            self._restore_session()
            self._navigate_home()
            self._handle_cloudflare()
            self._ensure_login()
            self._state = _State.READY
            self._log("GrokClient ready ✓")

        except Exception:
            # Clean up partial state so the caller can inspect or retry
            self._state = _State.STOPPED
            self._teardown_browser(quiet=True)
            raise

    def stop(self) -> None:
        """
        Gracefully close the browser and release all resources.
        Safe to call multiple times.
        """
        if self._state in (_State.STOPPING, _State.STOPPED):
            return

        self._state = _State.STOPPING
        self._log("Stopping GrokClient…")
        self._teardown_browser(quiet=False)
        self._state = _State.STOPPED
        self._log("GrokClient stopped.")

    def open_imagine(self) -> None:
        """
        Navigate to the Grok Imagine page and wait for the UI to load.

        Raises
        ------
        BrowserNotReadyError
            If the client is not in READY state.
        """
        self._assert_ready("open_imagine()")
        self._log("Opening Imagine page…")
        self._navigate_to(_GROK_IMAGINE)
        self._wait_for_ui()
        self._log("Imagine page ready ✓")

    def get_page(self) -> Page:
        """
        Return the active Playwright Page.

        Raises
        ------
        BrowserNotReadyError
            If the browser has not been started yet.
        """
        self._assert_ready("get_page()")
        return self._page  # type: ignore[return-value]

    def save_session(self) -> None:
        """
        Manually trigger a session cookie save.
        Useful after performing actions that may refresh session tokens.
        """
        self._assert_ready("save_session()")
        self._login_service.refresh_session()  # type: ignore[union-attr]
        self._log("Session saved manually.")

    @property
    def state(self) -> str:
        """Return the current lifecycle state as a string."""
        return self._state.name

    # ------------------------------------------------------------------
    # Browser lifecycle
    # ------------------------------------------------------------------

    def _launch_browser(self) -> None:
        """Initialise Playwright, launch Chromium, create context and page."""
        self._log("Launching browser…")

        self._playwright = sync_playwright().start()

        self._browser = self._playwright.chromium.launch(
            headless=False,
            args=_BROWSER_ARGS,
        )

        self._context = self._browser.new_context(
            viewport=None,
            user_agent=self._user_agent(),
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

        # Mask navigator.webdriver to reduce bot-detection fingerprint
        self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        self._page = self._context.new_page()
        self._page.set_default_navigation_timeout(_DEFAULT_NAVIGATION_TIMEOUT)
        self._page.set_default_timeout(_DEFAULT_PAGE_READY_TIMEOUT)

        self._log("Browser launched ✓")

    def _teardown_browser(self, quiet: bool) -> None:
        """
        Close page → context → browser → playwright in order.
        Swallows all exceptions if *quiet* is True.
        """
        for label, obj, method in [
            ("page",       self._page,       "close"),
            ("context",    self._context,    "close"),
            ("browser",    self._browser,    "close"),
            ("playwright", self._playwright, "stop"),
        ]:
            if obj is None:
                continue
            try:
                getattr(obj, method)()
            except Exception as exc:
                if not quiet:
                    logger.warning("[GrokClient] Error closing %s: %s", label, exc)

        self._page = self._context = self._browser = self._playwright = None
        self._login_service = None

    # ------------------------------------------------------------------
    # Session
    # ------------------------------------------------------------------

    def _restore_session(self) -> None:
        """Load saved cookies into the browser context (best-effort)."""
        try:
            cookies = self._session_manager.load()
        except Exception as exc:
            self._log(f"Session file corrupted, starting fresh. ({exc})")
            self._session_manager.clear()
            return

        if not cookies:
            self._log("No saved session — will need to log in.")
            return

        try:
            self._context.add_cookies(cookies)  # type: ignore[union-attr]
            self._log(f"Session restored ({len(cookies)} cookies) ✓")
        except Exception as exc:
            self._log(f"Could not apply saved cookies: {exc}")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _navigate_home(self) -> None:
        """Navigate to Grok home and wait for DOM to be ready."""
        self._log("Opening Grok home page…")
        self._navigate_to(_GROK_HOME)

    def _navigate_to(self, url: str, retries: int = 2) -> None:
        """
        Navigate to *url* with simple retry + exponential back-off.

        Parameters
        ----------
        url:
            Target URL.
        retries:
            Number of additional attempts after the first failure.
        """
        for attempt in range(retries + 1):
            try:
                self._page.goto(url, wait_until="domcontentloaded")  # type: ignore[union-attr]
                return
            except Exception as exc:
                if attempt == retries:
                    raise BrowserNotReadyError(
                        f"Failed to navigate to {url} after {retries + 1} attempts: {exc}"
                    ) from exc
                wait = 2 ** attempt
                self._log(f"Navigation failed (attempt {attempt + 1}), retrying in {wait}s…")
                time.sleep(wait)

    def _wait_for_ui(self) -> None:
        """Wait for the Grok textarea to appear (page fully rendered)."""
        try:
            self._page.wait_for_selector(  # type: ignore[union-attr]
                _UI_READY_SELECTOR,
                timeout=_DEFAULT_PAGE_READY_TIMEOUT,
            )
        except Exception:
            self._log("UI not detected — checking for Cloudflare…")
            self._handle_cloudflare()

    # ------------------------------------------------------------------
    # Cloudflare verification
    # ------------------------------------------------------------------

    def _handle_cloudflare(self) -> None:
        """
        Detect Cloudflare challenge and block until the user solves it.

        Detection uses multiple signals:
            1. Page HTML contains known CF strings.
            2. Page title matches CF challenge pattern.
            3. URL suggests CF interstitial.

        Raises
        ------
        TimeoutError
            If the user does not solve the challenge within
            *verification_timeout* seconds.
        """
        if not self._is_cloudflare_page():
            return

        self._log("⚠ Cloudflare verification detected — please solve it in the browser.")

        deadline = time.monotonic() + self._verification_timeout

        while self._is_cloudflare_page():
            remaining = int(deadline - time.monotonic())

            if remaining <= 0:
                raise TimeoutError(
                    f"Cloudflare verification not completed within "
                    f"{self._verification_timeout}s."
                )

            self._log(f"Waiting for verification… ({remaining}s remaining)")
            time.sleep(3)

        self._log("Cloudflare verification passed ✓")

    def _is_cloudflare_page(self) -> bool:
        """Return True if the current page shows a Cloudflare challenge."""
        try:
            html  = self._page.content().lower()   # type: ignore[union-attr]
            title = self._page.title().lower()      # type: ignore[union-attr]
            url   = self._page.url.lower()          # type: ignore[union-attr]

            return any(
                signal in text
                for signal in _CF_SIGNALS
                for text in (html, title, url)
            )
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def _ensure_login(self) -> None:
        """
        Create LoginService and delegate the full login + persist flow.

        Raises
        ------
        LoginTimeoutError
        BrowserNotReadyError
        """
        self._login_service = LoginService(
            page=self._page,
            session_manager=self._session_manager,
            selectors=self._login_selectors,
            log_callback=self._log,
        )
        self._login_service.ensure_logged_in()

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------

    def _assert_ready(self, method: str) -> None:
        if self._state is not _State.READY:
            raise BrowserNotReadyError(
                f"{method} requires state=READY, current state={self._state.name}. "
                "Call start() first."
            )

    def _assert_state(self, expected: _State, method: str) -> None:
        if self._state is not expected:
            raise RuntimeError(
                f"{method} expects state={expected.name}, "
                f"current state={self._state.name}."
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _user_agent() -> str:
        return (
            f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{_CHROME_VERSION} Safari/537.36"
        )