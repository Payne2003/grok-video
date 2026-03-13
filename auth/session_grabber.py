
"""
auth/session_grabber.py

Lấy cookie từ Chrome debug và kiểm tra xem user đã đăng nhập Grok hay chưa
dựa trên cookie session thật của hệ thống.

Cookie xác nhận login:
    sso
    x-userid
"""

import json
import logging
import os
import shutil
import subprocess
import sys
from PySide6.QtCore import QThread, Signal
from auth.chrome_launcher import is_port_open
from auth.session_manager import SessionManager

logger = logging.getLogger(__name__)

_ACCOUNTS_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "accounts"
)


# -------------------------------------------------
# Helper functions
# -------------------------------------------------

def get_cookie(cookies: list, name: str):
    for c in cookies:
        if c.get("name") == name:
            return c
    return None


def is_logged_in(cookies: list) -> bool:
    """
    Kiểm tra login dựa trên cookie session Grok
    """

    sso_cookie = get_cookie(cookies, "sso")
    userid_cookie = get_cookie(cookies, "x-userid")

    if sso_cookie and userid_cookie:
        return True

    return False


def get_user_id_from_cookies(cookies: list):
    c = get_cookie(cookies, "x-userid")
    return c.get("value") if c else None


def is_duplicate_session(cookies: list, current_slot: str):

    new_id = get_user_id_from_cookies(cookies)

    if not new_id:
        return None

    if not os.path.exists(_ACCOUNTS_ROOT):
        return None

    for acc in os.listdir(_ACCOUNTS_ROOT):

        if acc == current_slot:
            continue

        session_file = os.path.join(
            _ACCOUNTS_ROOT,
            acc,
            "session_state.json"
        )

        if not os.path.exists(session_file):
            continue

        try:

            with open(session_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            old_id = get_user_id_from_cookies(
                data.get("cookies", [])
            )

            if old_id and old_id == new_id:
                return acc

        except Exception:
            continue

    return None

def close_chrome_debug(port: int):
    """
    Tắt Chrome đang chạy với remote-debugging-port
    """

    try:

        if sys.platform.startswith("win"):

            subprocess.run(
                f'for /f "tokens=5" %a in (\'netstat -ano ^| findstr :{port}\') do taskkill /F /PID %a',
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

        else:

            subprocess.run(
                f"lsof -ti:{port} | xargs kill -9",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

    except Exception:
        pass
# -------------------------------------------------
# Worker
# -------------------------------------------------

class SessionGrabberWorker(QThread):

    log = Signal(str)
    finished = Signal(str, bool, str)

    def __init__(self, slot: str, port: int, session_manager: SessionManager):
        super().__init__()
        self.slot = slot
        self.port = port
        self._mgr = session_manager

    def run(self):

        slot = self.slot
        account_dir = os.path.join(_ACCOUNTS_ROOT, slot)

        success = False

        try:

            # kiểm tra chrome debug
            if not is_port_open(self.port):

                msg = f"Chrome port {self.port} chưa mở"

                self.log.emit(f"[{slot}] ❌ {msg}")
                self.finished.emit(slot, False, msg)

                return

            self.log.emit(f"[{slot}] 🔗 Kết nối Chrome {self.port}")

            from playwright.sync_api import sync_playwright

            with sync_playwright() as pw:

                browser = pw.chromium.connect_over_cdp(
                    f"http://127.0.0.1:{self.port}"
                )

                ctx = browser.contexts[0] if browser.contexts else None

                if not ctx:
                    raise RuntimeError("Không tìm thấy browser context")

                page = ctx.pages[0] if ctx.pages else ctx.new_page()

                # đảm bảo domain cookie được load
                page.goto(
                    "https://grok.com",
                    wait_until="domcontentloaded"
                )

                # lấy cookies
                cookies = ctx.cookies()

                if not cookies:
                    raise RuntimeError("Không lấy được cookies")

                # debug cookie
                for c in cookies:
                    self.log.emit(
                        f"[{slot}] COOKIE {c['name']} ({c['domain']})"
                    )

                # kiểm tra login
                if not is_logged_in(cookies):

                    msg = (
                        "Bạn chưa đăng nhập Grok.\n"
                        "Hãy đăng nhập trong Chrome rồi thử lại."
                    )

                    self.log.emit(f"[{slot}] ⚠️ {msg}")
                    self.finished.emit(slot, False, msg)

                    return

                self.log.emit(f"[{slot}] ✅ Phát hiện session login")

                # lọc cookie liên quan
                grok_cookies = [
                    c for c in cookies
                    if "grok.com" in c.get("domain", "")
                ]

                if len(grok_cookies) < 2:
                    raise RuntimeError(
                        "Cookie Grok không đủ"
                    )

                self.log.emit(
                    f"[{slot}] 🍪 {len(grok_cookies)} cookies"
                )

                # check duplicate
                dup_slot = is_duplicate_session(
                    grok_cookies,
                    slot
                )

                if dup_slot:

                    msg = f"Session trùng với [{dup_slot}]"

                    self.log.emit(f"[{slot}] ⚠️ {msg}")
                    self.finished.emit(slot, False, msg)

                    return

                # lưu session
                os.makedirs(account_dir, exist_ok=True)

                session_file = os.path.join(
                    account_dir,
                    "session_state.json"
                )

                mgr = SessionManager(session_file=session_file)

                mgr.save(grok_cookies)

                success = True

                msg = (
                    f"Session đã lưu ({len(grok_cookies)} cookies)"
                )

                self.log.emit(f"[{slot}] ✅ {msg}")
                self.finished.emit(slot, True, msg)
                close_chrome_debug(self.port)
                self.log.emit(f"[{slot}] 🔌 Đã đóng Chrome port {self.port}")

        except Exception as e:

            msg = str(e)

            self.log.emit(f"[{slot}] ❌ Lỗi: {msg}")
            self.finished.emit(slot, False, msg)

        finally:

            if not success:

                self.log.emit(
                    f"[{slot}] ℹ️ Giữ nguyên dữ liệu để người dùng tiếp tục đăng nhập"
                )
