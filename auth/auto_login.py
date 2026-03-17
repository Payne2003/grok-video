"""
auth/auto_login.py
──────────────────
Tự động đăng nhập accounts.x.ai dùng các class sẵn có trong project:
  - ChromeLauncher   (auth/chrome_launcher.py)  → mở Chrome
  - SessionManager   (auth/session_manager.py)  → lưu cookies
  - AccountStore     (accounts/account_store.py) → lấy email/password
  - info.json        (accounts/<slot>/info.json) → fallback credentials

Chiến lược:
  - Email, Password, Button  → DOM selector qua Playwright CDP
  - Cloudflare Turnstile      → tọa độ màn hình (bắt buộc vì iframe sandbox)
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# ── Chỉ dùng pyautogui cho Cloudflare click ───────────────────
try:
    import pyautogui as pg
    pg.FAILSAFE = False
    pg.PAUSE    = 0.0
    HAS_PG = True
except ImportError:
    HAS_PG = False

# ── Import các class sẵn có trong project ─────────────────────
from auth.chrome_launcher import ChromeLauncher, slot_to_port, slot_to_profile, is_port_open
from auth.session_manager import SessionManager

# ────────────────────────────────────────────────────────────────
#  CONFIG
# ────────────────────────────────────────────────────────────────

LOGIN_URL   = "https://accounts.x.ai/sign-in?redirect=grok-com&email=true"
COORDS_FILE = str(Path(__file__).parent.parent / "config" / "coords.json")

DEFAULT_COORDS: dict = {
    "cloudflare_check": [640, 422],
}

# DOM selectors cho trang accounts.x.ai
SELECTORS = {
    "email": [
        'input[type="email"]',
        'input[name="email"]',
        'input[autocomplete="email"]',
        'input[placeholder*="mail" i]',
        'input[placeholder*="e-mail" i]',
    ],
    # Nút Continue/Next — button submit đầu tiên trên trang (bất kể ngôn ngữ)
    "continue_btn": [
        'button[type="submit"]',
        'button[role="button"][type="submit"]',
        'form button:last-of-type',
    ],
    "password": [
        'input[type="password"]',
        'input[name="password"]',
        'input[autocomplete="current-password"]',
        'input[autocomplete="new-password"]',
    ],
    # Nút Sign in / Connexion / Đăng nhập... — button submit bất kể ngôn ngữ
    "signin_btn": [
        'button[type="submit"]',
        'button[role="button"][type="submit"]',
        'form button:last-of-type',
    ],
}


# ────────────────────────────────────────────────────────────────
#  COORDS MANAGER
# ────────────────────────────────────────────────────────────────

def load_coords() -> dict:
    path = Path(COORDS_FILE)
    if path.exists():
        try:
            return {k: list(v) for k, v in
                    json.loads(path.read_text(encoding="utf-8")).items()}
        except Exception:
            pass
    return DEFAULT_COORDS.copy()


def save_coords(coords: dict):
    path = Path(COORDS_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(coords, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


# ────────────────────────────────────────────────────────────────
#  ĐỌC CREDENTIALS TỪ info.json CỦA TỪNG ACCOUNT
# ────────────────────────────────────────────────────────────────

def load_credentials_from_slot(slot: str) -> tuple[str, str]:
    """
    Đọc email + password từ accounts/<slot>/info.json.
    Trả về (email, password).
    """
    base = Path(__file__).parent.parent / "accounts" / slot / "info.json"
    if base.exists():
        try:
            data = json.loads(base.read_text(encoding="utf-8"))
            return data.get("email", ""), data.get("password", "")
        except Exception:
            pass
    return "", ""


# ────────────────────────────────────────────────────────────────
#  DOM HELPERS
# ────────────────────────────────────────────────────────────────

def _find_el(page, selectors: list, timeout: int = 8000):
    for sel in selectors:
        try:
            el = page.wait_for_selector(sel, state="visible", timeout=timeout)
            if el:
                return el, sel
        except Exception:
            continue
    return None, None


def _dom_fill(page, selectors: list, text: str,
               log: Callable, label: str, mask: bool = False) -> bool:
    """Tìm input bằng DOM → điền text như người gõ. Không di chuột."""
    el, sel = _find_el(page, selectors)
    if not el:
        log(f"  ❌ Không tìm thấy [{label}]")
        _dump_inputs(page, log)
        return False

    display = "*" * len(text) if mask else text
    log(f"  ⌨️  [{label}] → gõ: {display[:30]}")

    try:
        el.click()
        time.sleep(random.uniform(0.1, 0.2))
        el.evaluate("e => { e.value = ''; e.dispatchEvent(new Event('input')); }")
        time.sleep(random.uniform(0.05, 0.1))
        for ch in text:
            el.type(ch, delay=random.randint(45, 110))
        time.sleep(random.uniform(0.2, 0.4))
        return True
    except Exception as e:
        log(f"  ⚠️  Lỗi fill [{label}]: {e}")
        return False


def _dom_click(page, selectors: list, log: Callable, label: str) -> bool:
    """
    Tìm button bằng DOM → click.
    Ưu tiên button visible + enabled + không bị disabled.
    Không quan tâm text hiển thị (bất kể ngôn ngữ).
    """
    # Thử từng selector, lấy button visible + enabled đầu tiên
    for sel in selectors:
        try:
            els = page.query_selector_all(sel)
            for el in els:
                try:
                    if el.is_visible() and el.is_enabled():
                        log(f"  🖱  [{label}] click → {sel}")
                        el.click()
                        return True
                except Exception:
                    continue
        except Exception:
            continue

    # Fallback JS: tìm button submit visible đầu tiên trong DOM
    try:
        clicked = page.evaluate("""() => {
            const btns = [...document.querySelectorAll(
                'button[type="submit"], button[role="button"]'
            )];
            const btn = btns.find(b =>
                b.offsetParent !== null &&
                !b.disabled &&
                !b.getAttribute('disabled')
            );
            if (btn) { btn.click(); return true; }
            return false;
        }""")
        if clicked:
            log(f"  🖱  [{label}] click via JS fallback")
            return True
    except Exception:
        pass

    log(f"  ❌ Không tìm thấy [{label}]")
    return False


def _dump_inputs(page, log: Callable):
    """Debug: in ra tất cả input đang có trên trang."""
    try:
        items = page.evaluate("""() =>
            [...document.querySelectorAll('input')].map(e => ({
                type: e.type, name: e.name,
                placeholder: e.placeholder,
                visible: e.offsetParent !== null
            }))
        """)
        log(f"  DEBUG inputs ({len(items)}):")
        for it in items:
            if it.get("visible"):
                log(f"    type={it['type']} name={it['name']} ph={it['placeholder']}")
    except Exception:
        pass


def _dump_buttons(page, log: Callable):
    """Debug: in ra tất cả button đang có trên trang."""
    try:
        items = page.evaluate("""() =>
            [...document.querySelectorAll('button')].map(b => ({
                type:     b.type,
                text:     b.innerText.trim().slice(0, 40),
                disabled: b.disabled,
                visible:  b.offsetParent !== null
            }))
        """)
        log(f"  DEBUG buttons ({len(items)}):")
        for it in items:
            if it.get("visible"):
                log(f"    type={it['type']} disabled={it['disabled']} "
                    f"text='{it['text']}'")
    except Exception:
        pass


def _click_submit_btn(page, log: Callable) -> bool:
    """
    Click nút submit đầu tiên visible + enabled — bất kể text ngôn ngữ gì.
    Ưu tiên: type=submit → fallback JS click.
    """
    # Cách 1: Playwright query tất cả button, lọc visible+enabled
    try:
        result = page.evaluate("""() => {
            // Ưu tiên button[type=submit] visible + không disabled
            const all = [
                ...document.querySelectorAll('button[type="submit"]'),
                ...document.querySelectorAll('button:not([type])'),
                ...document.querySelectorAll('input[type="submit"]'),
            ];
            for (const btn of all) {
                if (btn.offsetParent !== null
                    && !btn.disabled
                    && !btn.hasAttribute('disabled')) {
                    btn.click();
                    return btn.innerText || btn.value || 'clicked';
                }
            }
            return null;
        }""")
        if result:
            log(f"  🖱  Đã click nút: '{result}'")
            return True
    except Exception as e:
        log(f"  ⚠️  JS click lỗi: {e}")

    # Cách 2: Playwright locator
    try:
        btn = page.locator('button[type="submit"]').first
        if btn and btn.is_visible() and btn.is_enabled():
            btn.click()
            log(f"  🖱  Playwright click button[type=submit]")
            return True
    except Exception:
        pass

    # Cách 3: Enter key — hầu hết form đều submit khi nhấn Enter
    try:
        log(f"  ⌨️  Fallback: nhấn Enter")
        page.keyboard.press("Enter")
        return True
    except Exception as e:
        log(f"  ❌ Enter cũng lỗi: {e}")

    return False


# ────────────────────────────────────────────────────────────────
#  CLOUDFLARE — phải dùng tọa độ vì là iframe sandbox
# ────────────────────────────────────────────────────────────────

def _detect_cf(page) -> bool:
    """Phát hiện CF Turnstile trong DOM."""
    try:
        return bool(page.evaluate("""() => {
            const frames = [...document.querySelectorAll('iframe')];
            return frames.some(f =>
                (f.src||'').includes('challenges.cloudflare.com') ||
                (f.src||'').includes('turnstile')
            ) || !!document.querySelector(
                '[class*="turnstile"],[id*="turnstile"],cf-turnstile'
            );
        }"""))
    except Exception:
        return False


def handle_cloudflare(page, coords: dict,
                       log: Callable, max_wait: int = 60) -> bool:
    """
    Phát hiện CF qua DOM → click tọa độ → chờ CF biến mất khỏi DOM.
    Trả về True nếu không có CF hoặc đã qua được.
    """
    log("  🛡  Kiểm tra Cloudflare...")

    # Chờ tối đa 6s xem CF có xuất hiện không
    cf_found = False
    for _ in range(6):
        if _detect_cf(page):
            cf_found = True
            break
        time.sleep(1.0)

    if not cf_found:
        log("  ✅ Không có Cloudflare")
        return True

    log("  🛡  Phát hiện CF Turnstile!")

    cf = coords.get("cloudflare_check")
    if not cf:
        log("  ⚠️  Chưa cấu hình tọa độ — nhấn 🎯 Tọa độ trong UI")
        return False

    if not HAS_PG:
        log("  ⚠️  pyautogui chưa cài — pip install pyautogui")
        return False

    # Click checkbox CF bằng tọa độ
    cx, cy = int(cf[0]), int(cf[1])
    log(f"  🖱  Click CF checkbox ({cx}, {cy})")
    time.sleep(random.uniform(0.5, 1.0))
    pg.moveTo(cx + random.randint(-2, 2), cy + random.randint(-2, 2),
              duration=random.uniform(0.3, 0.5), tween=pg.easeInOutQuad)
    time.sleep(random.uniform(0.1, 0.2))
    pg.click(cx, cy)

    # Chờ CF biến mất
    log("  ⏳ Chờ CF xác minh...")
    for i in range(max_wait):
        time.sleep(1.0)
        if not _detect_cf(page):
            log(f"  ✅ CF xong sau {i+1}s")
            time.sleep(1.5)
            return True
        if i > 0 and i % 10 == 0:
            log(f"  ⏳ Chờ CF... ({i}s)")

    log("  ⚠️  CF timeout — thử tiếp")
    return False


# ────────────────────────────────────────────────────────────────
#  MAIN LOGIN FLOW
# ────────────────────────────────────────────────────────────────

@dataclass
class LoginConfig:
    slot        : str
    email       : str       = ""
    password    : str       = ""
    coords      : dict      = field(default_factory=load_coords)

    def __post_init__(self):
        # Nếu email/password rỗng → đọc từ info.json của slot
        if not self.email or not self.password:
            e, p = load_credentials_from_slot(self.slot)
            if not self.email:    self.email    = e
            if not self.password: self.password = p


def run_auto_login(cfg: LoginConfig,
                    log: Callable = print,
                    is_cancelled: Callable = lambda: False) -> dict:
    """
    Đăng nhập accounts.x.ai dùng ChromeLauncher + Playwright CDP.

    Flow:
      0. Xóa cookies accounts.x.ai + grok.com trong profile (tránh session cũ)
      1. ChromeLauncher.open()  → mở Chrome (profile riêng cho từng slot)
      2. Playwright kết nối CDP
      3. Phát hiện + xử lý Cloudflare
      4. DOM fill email → DOM click Continue
      5. DOM fill password → DOM click Sign in
      6. Chờ redirect → grok.com
    """
    from playwright.sync_api import sync_playwright

    R = {"slot": cfg.slot, "status": "error", "message": ""}
    coords = cfg.coords or load_coords()

    if not cfg.email or not cfg.password:
        return {**R, "message": f"Không có email/password cho {cfg.slot}"}

    try:
        if is_cancelled(): return {**R, "message": "Cancelled"}

        # ── 1. Mở Chrome (mỗi slot dùng profile riêng → song song được) ──
        log(f"[{cfg.slot}] 🚀 Mở Chrome port={slot_to_port(cfg.slot)}")
        launcher = ChromeLauncher(cfg.slot)
        port     = launcher.open(url=LOGIN_URL, wait=15.0)
        log(f"[{cfg.slot}] ✅ Chrome port={port}")

        time.sleep(2.5)
        if is_cancelled(): return {**R, "message": "Cancelled"}

        # ── 2. Kết nối Playwright CDP ─────────────────────────────
        log(f"[{cfg.slot}] 🔗 Kết nối Playwright...")
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(launcher.cdp_url)
            ctx  = browser.contexts[0] if browser.contexts else browser.new_context()
            page = ctx.pages[0]       if ctx.pages        else ctx.new_page()

            # ── XÓA COOKIES CŨ → tránh giữ session account trước ──
            log(f"[{cfg.slot}] 🧹 Xóa cookies cũ (x.ai + grok.com)...")
            try:
                ctx.clear_cookies()
                log(f"[{cfg.slot}] ✅ Đã xóa cookies")
            except Exception as e:
                log(f"[{cfg.slot}] ⚠️  Xóa cookies lỗi: {e}")

            # Navigate về trang login sạch
            log(f"[{cfg.slot}] 🔀 Navigate → login page")
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(2.5)

            if is_cancelled(): return {**R, "message": "Cancelled"}

            # ── 3. Cloudflare lần đầu (nếu xuất hiện trước khi nhập) ──
            handle_cloudflare(page, coords, log, max_wait=30)
            time.sleep(1.0)
            if is_cancelled(): return {**R, "message": "Cancelled"}

            # ── 4. Nhập email ─────────────────────────────────────
            log(f"[{cfg.slot}] 📧 Nhập email")
            if not _dom_fill(page, SELECTORS["email"],
                              cfg.email, log, "email"):
                return {**R, "message": "Không tìm thấy ô email"}
            time.sleep(random.uniform(0.3, 0.5))

            # ── 5. Nhập password (cùng trang hoặc sau Continue) ───
            pw_el, _ = _find_el(page, SELECTORS["password"], timeout=2000)
            if not pw_el:
                log(f"[{cfg.slot}] ➡️  Click Continue")
                _dom_click(page, SELECTORS["continue_btn"], log, "Continue")
                try:
                    page.wait_for_selector('input[type="password"]',
                                           state="visible", timeout=12000)
                except Exception:
                    time.sleep(3.5)
            else:
                log(f"[{cfg.slot}] ℹ️  Email + Password cùng 1 trang")

            if is_cancelled(): return {**R, "message": "Cancelled"}

            log(f"[{cfg.slot}] 🔑 Nhập password")
            if not _dom_fill(page, SELECTORS["password"],
                              cfg.password, log, "password", mask=True):
                return {**R, "message": "Không tìm thấy ô password"}
            time.sleep(random.uniform(0.4, 0.6))

            # ── 6. Cloudflare lần 2 (xuất hiện SAU khi nhập) ──────
            # Nhìn ảnh: CF tick xong mới enable nút Connexion
            handle_cloudflare(page, coords, log, max_wait=60)
            time.sleep(1.0)
            if is_cancelled(): return {**R, "message": "Cancelled"}

            # ── 7. Dump tất cả button để debug, rồi click ─────────
            _dump_buttons(page, log)

            log(f"[{cfg.slot}] 🖱  Click nút đăng nhập")
            clicked = _click_submit_btn(page, log)
            if not clicked:
                return {**R, "message": "Không tìm thấy nút đăng nhập"}

            # ── 8. Chờ redirect ───────────────────────────────────
            log(f"[{cfg.slot}] ⏳ Chờ redirect về grok.com...")
            try:
                page.wait_for_url("*grok.com*", timeout=15000)
            except Exception:
                time.sleep(5.0)

            log(f"[{cfg.slot}] ✅ Đăng nhập xong | URL: {page.url}")
            return {**R, "status": "success", "message": "Đăng nhập thành công"}

    except Exception as e:
        log(f"[{cfg.slot}] ❌ {e}")
        return {**R, "message": str(e)}


# ────────────────────────────────────────────────────────────────
#  CHẠY SONG SONG TẤT CẢ ACCOUNTS
# ────────────────────────────────────────────────────────────────

def run_all_parallel(slots: list[str],
                      log: Callable = print,
                      is_cancelled: Callable = lambda: False,
                      on_slot_done: Callable = None) -> list[dict]:
    """
    Chạy auto login cho tất cả slots CÙNG LÚC.
    Mỗi slot có ChromeLauncher riêng → port riêng → profile riêng
    → hoàn toàn độc lập, không ảnh hưởng nhau.

    on_slot_done(slot, ok, message) được gọi sau mỗi slot xong.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    coords  = load_coords()
    configs = []
    for slot in slots:
        cfg = LoginConfig(slot=slot, coords=coords)
        if not cfg.email or not cfg.password:
            log(f"[{slot}] ❌ Không có credentials → bỏ qua")
            continue
        configs.append(cfg)

    if not configs:
        log("❌ Không có account nào có credentials")
        return []

    log(f"🚀 Chạy song song {len(configs)} accounts...")
    results = []

    def _run_one(cfg):
        return run_auto_login(
            cfg          = cfg,
            log          = lambda m: log(m),
            is_cancelled = is_cancelled,
        )

    with ThreadPoolExecutor(max_workers=len(configs)) as pool:
        futures = {pool.submit(_run_one, cfg): cfg for cfg in configs}
        for future in as_completed(futures):
            cfg    = futures[future]
            result = future.result()
            results.append(result)
            ok  = result["status"] == "success"
            msg = result["message"]
            log(f"{'✅' if ok else '❌'} [{cfg.slot}] {msg}")
            if on_slot_done:
                try:
                    on_slot_done(cfg.slot, ok, msg)
                except Exception:
                    pass

    done  = sum(1 for r in results if r["status"] == "success")
    total = len(results)
    log(f"🏁 Song song xong: {done}/{total} thành công")
    return results


# ────────────────────────────────────────────────────────────────
#  QThread WORKER — dùng trong login_panel.py
# ────────────────────────────────────────────────────────────────

from PySide6.QtCore import QThread, Signal


class AutoLoginWorker(QThread):
    """Worker cho 1 account."""
    log_msg  = Signal(str)
    finished = Signal(str, bool, str)

    def __init__(self, cfg: LoginConfig, parent=None):
        super().__init__(parent)
        self.cfg        = cfg
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        result = run_auto_login(
            cfg          = self.cfg,
            log          = self.log_msg.emit,
            is_cancelled = lambda: self._cancelled,
        )
        self.finished.emit(
            self.cfg.slot,
            result["status"] == "success",
            result["message"]
        )


class AutoLoginAllWorker(QThread):
    """Worker chạy song song TẤT CẢ accounts cùng lúc."""
    log_msg     = Signal(str)
    slot_done   = Signal(str, bool, str)   # (slot, ok, message)
    all_done    = Signal()

    def __init__(self, slots: list[str], parent=None):
        super().__init__(parent)
        self.slots      = slots
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        run_all_parallel(
            slots        = self.slots,
            log          = self.log_msg.emit,
            is_cancelled = lambda: self._cancelled,
            on_slot_done = self.slot_done.emit,
        )
        self.all_done.emit()