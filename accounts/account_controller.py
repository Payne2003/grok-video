"""
accounts/account_controller.py
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from accounts.account_store import AccountStore
from auth.chrome_launcher import slot_to_port, is_port_open


@dataclass
class AccountRow:
    index:       int
    slot:        str
    email:       str
    status:      str
    last_login:  str
    cookies:     str
    has_session: bool
    port:        int    # debug port của account


class AccountController:
    def __init__(self, store: Optional[AccountStore] = None):
        self._store            = store or AccountStore()
        self._login_workers:   Dict[str, object] = {}   # slot → LoginWorker
        self._grabber_workers: Dict[str, object] = {}   # slot → SessionGrabberWorker
        self._listeners: List[Callable] = []
        self._store.on_change(self._broadcast)

    # ── Observer ─────────────────────────────────────────────────

    def on_data_changed(self, fn: Callable): self._listeners.append(fn)
    def _broadcast(self):
        for fn in self._listeners:
            try: fn()
            except Exception: pass

    # ── Query ────────────────────────────────────────────────────

    def get_rows(self) -> List[AccountRow]:
        rows = []
        for i, acc in enumerate(self._store.all(), start=1):
            rows.append(AccountRow(
                index       = i,
                slot        = acc.slot,
                email       = acc.email,
                status      = acc.status,
                last_login  = acc.last_login_short,
                cookies     = str(acc.cookie_count) if acc.session_exists else "-",
                has_session = acc.session_exists,
                port        = slot_to_port(acc.slot),
            ))
        return rows

    def total(self)        -> int: return self._store.count()
    def total_logged(self) -> int: return self._store.count_logged()

    def get_email_by_slot(self, slot: str) -> str:
        acc = self._store.get_by_slot(slot)
        return acc.email if acc else ""

    def get_password_by_slot(self, slot: str) -> str:
        acc = self._store.get_by_slot(slot)
        return acc.password if acc else ""

    def get_port(self, slot: str) -> int:
        return slot_to_port(slot)

    def is_chrome_open(self, slot: str) -> bool:
        return is_port_open(self.get_port(slot))

    # ── CRUD ─────────────────────────────────────────────────────

    def add(self, email: str, password: str) -> tuple[bool, str]:
        email = email.strip()
        if not email:           return False, "Email không được để trống"
        if "@" not in email:    return False, "Email không hợp lệ"
        result = self._store.add(email, password)
        if result is None:      return False, f"Email '{email}' đã tồn tại"
        return True, f"Đã thêm: {email} → {result.slot}"

    def edit(self, slot: str, new_password: str) -> tuple[bool, str]:
        ok = self._store.update(slot, password=new_password)
        if not ok: return False, f"Không tìm thấy {slot}"
        return True, f"Đã cập nhật: {self.get_email_by_slot(slot)}"

    def delete(self, slots: List[str]) -> tuple[int, str]:
        deleted = sum(1 for s in slots if self._store.delete(s))
        return deleted, f"Đã xóa {deleted} tài khoản"

    def delete_all(self) -> str:
        n = self._store.count()
        self._store.delete_all()
        return f"Đã xóa tất cả {n} tài khoản"

    def logout(self, slots: List[str]) -> str:
        for s in slots: self._store.clear_session(s)
        return f"Đã logout {len(slots)} tài khoản"

    def import_txt(self, path: str) -> str:
        return f"Import xong: +{self._store.import_from_txt(path)} tài khoản"

    def export_txt(self, path: str) -> str:
        self._store.export_to_txt(path)
        return f"Export xong → {path}"

    # ── Bước 1: Mở Chrome ────────────────────────────────────────

    def start_login(self, slot: str,
                    on_log: Callable,
                    on_chrome_ready: Callable,   # (slot, port)
                    on_failed: Callable):         # (slot, msg)
        if slot in self._login_workers:
            on_log(f"[{slot}] ⚠️  Chrome đang mở, bỏ qua")
            return

        from auth.login_worker import LoginWorker
        w = LoginWorker(slot)
        w.log.connect(on_log)
        w.chrome_ready.connect(lambda s, p: self._on_chrome_ready(s, p, on_chrome_ready))
        w.failed.connect(lambda s, m: self._on_login_failed(s, m, on_failed))
        self._login_workers[slot] = w
        w.start()

    def _on_chrome_ready(self, slot, port, cb):
        self._login_workers.pop(slot, None)
        try: cb(slot, port)
        except Exception: pass

    def _on_login_failed(self, slot, msg, cb):
        self._login_workers.pop(slot, None)
        try: cb(slot, msg)
        except Exception: pass

    # ── Bước 2: Lưu Session ──────────────────────────────────────

    def save_session(self, slot: str,
                     on_log: Callable,
                     on_done: Callable):    # (slot, ok, msg)
        if slot in self._grabber_workers:
            on_log(f"[{slot}] ⚠️  Đang lưu session, chờ xíu...")
            return

        port    = self.get_port(slot)
        session = self._store.get_session_manager(slot)

        from auth.session_grabber import SessionGrabberWorker
        w = SessionGrabberWorker(slot, port, session)
        w.log.connect(on_log)
        w.finished.connect(lambda s, ok, msg: self._on_grab_done(s, ok, msg, on_done))
        self._grabber_workers[slot] = w
        w.start()

    def _on_grab_done(self, slot, ok, msg, cb):
        self._grabber_workers.pop(slot, None)
        if ok:
            self._broadcast()   # refresh UI → badge logged_in
        try: cb(slot, ok, msg)
        except Exception: pass