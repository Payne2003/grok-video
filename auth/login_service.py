"""auth/login_service.py — Orchestrates Grok login and session persistence."""

import logging, time
from dataclasses import dataclass, field
from typing import Callable, Optional
from playwright.sync_api import Page
from auth.exceptions import BrowserNotReadyError, LoginTimeoutError
from auth.session_manager import SessionManager

logger = logging.getLogger(__name__)


class LoginService:
    """
    Chờ user đăng nhập thủ công, xác nhận thật sự đã vào được Grok,
    rồi mới lưu session.
    Hỗ trợ mọi phương thức đăng nhập: Google, X, email, v.v.
    """

    def __init__(
        self,
        page: Page,
        session_manager: Optional[SessionManager] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        timeout: float = 300.0,
        poll_interval: float = 2.0,
    ) -> None:
        if page is None:
            raise BrowserNotReadyError("Cần truyền Playwright Page hợp lệ.")
        self._page    = page
        self._mgr     = session_manager or SessionManager()
        self._log     = log_callback or (lambda m: logger.info("[LoginService] %s", m))
        self._timeout = timeout
        self._poll    = poll_interval

    # ── Public ──────────────────────────────────────────────────

    def ensure_logged_in(self) -> None:
        """
        Flow manual login:
        1. Mở Grok
        2. Dừng tool
        3. User đăng nhập + giải captcha
        4. Nhấn ENTER
        5. Tool verify login
        6. Lưu session
        """

        self._log("Mở trang Grok để đăng nhập...")
        try:
            self._page.goto("https://grok.com", wait_until="load", timeout=30000)
        except:
            pass

        self._log("""
    ╔══════════════════════════════════════════════╗
    ║            ĐĂNG NHẬP THỦ CÔNG GROK           ║
    ╠══════════════════════════════════════════════╣
    ║ 1. Đăng nhập Grok trong cửa sổ Chrome       ║
    ║ 2. Giải CAPTCHA nếu có                      ║
    ║ 3. Khi đã vào được Grok chat/imagine        ║
    ║ 4. Quay lại terminal và nhấn ENTER          ║
    ╚══════════════════════════════════════════════╝
    """)

        input(">> Nhấn ENTER sau khi đã đăng nhập xong...")

        # verify login
        if not self._confirm_logged_in():
            raise LoginTimeoutError(
                "Không phát hiện đăng nhập Grok. Hãy đảm bảo bạn đã vào /chat hoặc /imagine."
            )

        self._log("🎉 Đăng nhập thành công — lưu session...")
        self._save_session_verified()


    def refresh_session(self) -> None:
        self._save_session_verified()
        self._log("Session đã được refresh.")

    def logout(self) -> None:
        self._mgr.clear()
        self._log("Session đã xoá.")

    # ── Xác nhận đã vào Grok thật sự ───────────────────────────

    def _confirm_logged_in(self) -> bool:
        """
        Xác nhận chắc chắn đã đăng nhập bằng cách:
        1. Kiểm tra URL hiện tại
        2. Kiểm tra DOM — có phần tử chỉ hiện khi logged in không
        3. Thử navigate đến /imagine và xem có redirect login không
        Trả True CHỈ KHI chắc chắn đã vào được.
        """
        try:
            url = self._page.url.lower()
            self._log(f"URL: {self._page.url}")

            # Đang ở trang login rõ ràng → chắc chắn chưa login
            if self._is_login_url(url):
                self._log("→ Đang ở trang login")
                return False

            # Kiểm tra DOM nhanh
            dom_result = self._check_dom_login_state()
            if dom_result is False:
                self._log("→ DOM cho thấy chưa login")
                return False

            # Thử navigate /imagine để xác nhận thật
            return self._verify_by_navigation()

        except Exception as e:
            self._log(f"Lỗi khi kiểm tra: {e}")
            return False

    def _is_login_url(self, url: str) -> bool:
        LOGIN_HINTS = (
            "x.com/i/flow", "twitter.com/i/flow",
            "accounts.google.com",
            "/login", "/signin", "/sign-in",
            "oauth", "/auth",
        )
        return any(h in url for h in LOGIN_HINTS)

    def _check_dom_login_state(self) -> Optional[bool]:
        """
        Trả về:
          True  → DOM có dấu hiệu đã login
          False → DOM có dấu hiệu chưa login
          None  → không xác định
        """
        try:
            result = self._page.evaluate("""() => {
                // Dấu hiệu ĐÃ login — chỉ render khi vào được Grok
                const loggedInHints = [
                    'a[href="/imagine"]',
                    'a[href*="/imagine"]',
                    'button[aria-label="New chat"]',
                    'a[aria-label="Grok"]',
                    '[data-testid="UserAvatar-Container"]',
                    '[aria-label="Account menu"]',
                    '[aria-label="Open sidebar"]',
                    'nav',
                ];
                for (const sel of loggedInHints) {
                    if (document.querySelector(sel)) return 'logged_in:' + sel;
                }

                // Dấu hiệu CHƯA login
                const loggedOutHints = [
                    'button:has-text("Sign in")',
                    'a[href*="login"]',
                    'input[name="username"]',
                    'input[autocomplete="username"]',
                    'input[name="password"]',
                ];
                for (const sel of loggedOutHints) {
                    try {
                        if (document.querySelector(sel)) return 'logged_out:' + sel;
                    } catch(e) {}
                }

                // Kiểm tra text
                const bodyText = document.body?.innerText?.toLowerCase() || '';
                if (bodyText.includes('sign in to') || bodyText.includes('log in to'))
                    return 'logged_out:text';
                if (bodyText.includes('imagine') && bodyText.includes('new chat'))
                    return 'logged_in:text';

                return 'unknown';
            }""")

            self._log(f"DOM check: {result}")
            if result and result.startswith("logged_in"):
                return True
            if result and result.startswith("logged_out"):
                return False
            return None
        except:
            return None

    def _verify_by_navigation(self) -> bool:
        """
        Điều hướng đến /imagine — nếu không bị redirect sang login → đã login thật.
        """
        try:
            current_url = self._page.url

            # Nếu đang ở /imagine rồi thì không cần navigate
            if "grok.com/imagine" in current_url or "grok.com/chat" in current_url:
                self._log("✅ Đang ở trang Grok — đã login")
                return True

            self._log("Kiểm tra bằng navigate /imagine...")
            self._page.goto("https://grok.com/imagine", wait_until="load", timeout=20000)
            time.sleep(2)

            final_url = self._page.url.lower()
            if self._is_login_url(final_url):
                self._log("→ Bị redirect sang login → chưa đăng nhập")
                return False

            if "grok.com" in final_url:
                self._log(f"✅ Vào được Grok: {self._page.url}")
                return True

            self._log(f"→ URL không xác định: {self._page.url}")
            return False

        except Exception as e:
            self._log(f"Lỗi navigate: {e}")
            return False

    # ── Chờ đăng nhập thủ công ──────────────────────────────────

    def _wait_for_login(self) -> None:
        deadline = time.monotonic() + self._timeout
        errors   = 0

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise LoginTimeoutError(
                    f"Hết {int(self._timeout)}s — chưa phát hiện đăng nhập."
                )

            try:
                url = self._page.url.lower()

                # Nếu đang ở trang login → nhắc nhở
                if self._is_login_url(url):
                    self._log(f"⏳ Chờ đăng nhập... ({int(remaining)}s còn)")
                    errors = 0
                    time.sleep(self._poll)
                    continue

                # URL đã chuyển khỏi login page → kiểm tra đã vào được chưa
                if self._confirm_logged_in():
                    self._log("🎉 Đăng nhập thành công!")
                    self._save_session_verified()
                    return

                # Chưa xác nhận được → tiếp tục chờ
                self._log(f"⏳ Đang kiểm tra... ({int(remaining)}s còn)")
                errors = 0

            except BrowserNotReadyError:
                raise
            except Exception as e:
                errors += 1
                self._log(f"⚠️  Lỗi kiểm tra ({errors}/3): {e}")
                if errors >= 3:
                    raise BrowserNotReadyError(f"Browser lỗi liên tiếp: {e}") from e

            time.sleep(self._poll)

    # ── Lưu session (chỉ gọi sau khi xác nhận login) ────────────

    def _save_session_verified(self) -> None:
        """
        Lấy cookies từ browser và lưu.
        Chỉ được gọi sau khi _confirm_logged_in() trả True.
        """
        try:
            cookies = self._page.context.cookies()
        except Exception as e:
            raise BrowserNotReadyError(f"Không lấy được cookies: {e}") from e

        if not cookies:
            raise BrowserNotReadyError("Browser không có cookies nào.")

        # Lọc chỉ lấy cookies liên quan
        relevant = [c for c in cookies
                    if any(d in c.get("domain", "")
                           for d in ["grok.com", "x.ai", "x.com",
                                     "twitter.com", "google.com"])]

        if not relevant:
            # Dùng tất cả nếu không lọc được
            relevant = cookies

        self._log(f"Lưu {len(relevant)} cookies (từ {len(cookies)} tổng)...")
        self._mgr.save(relevant)
        self._log(f"✅ Session đã lưu.")