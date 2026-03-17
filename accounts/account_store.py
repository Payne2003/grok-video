"""
accounts/account_store.py

Mỗi account = 1 folder:
    accounts/
        account_01/
            info.json          ← email, password, created_at
            session_state.json ← do SessionManager quản lý
        account_02/
            ...
"""

import json, os, re, shutil
from datetime import datetime
from typing import Callable, List, Optional

from auth.session_manager import SessionManager

_BASE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "accounts"
)


class AccountInfo:
    def __init__(self, slot: str, folder: str):
        self.slot             = slot
        self.folder           = folder
        self.email            = ""
        self.password         = ""
        self.created_at       = ""
        self.session_exists   = False
        self.session_saved_at: Optional[str] = None
        self.cookie_count     = 0

    @property
    def status(self) -> str:
        return "logged_in" if self.session_exists else "pending"

    @property
    def last_login_short(self) -> str:
        if not self.session_saved_at:
            return "-"
        try:
            return self.session_saved_at.replace("T", " ")[:16]
        except Exception:
            return "-"


class AccountStore:
    def __init__(self, base_dir: str = _BASE):
        self._base = base_dir
        os.makedirs(self._base, exist_ok=True)
        self._listeners: List[Callable] = []

    def on_change(self, fn: Callable):
        self._listeners.append(fn)

    def _notify(self):
        for fn in self._listeners:
            try: fn()
            except Exception: pass

    # ── Read ─────────────────────────────────────────────────────

    def all(self) -> List[AccountInfo]:
        result = []
        try:
            entries = sorted(os.listdir(self._base))
        except OSError:
            return result
        for name in entries:
            folder = os.path.join(self._base, name)
            if os.path.isdir(folder) and re.match(r"^account_\d+$", name):
                result.append(self._load_one(name, folder))
        return result

    def _load_one(self, slot: str, folder: str) -> AccountInfo:
        acc = AccountInfo(slot=slot, folder=folder)
        info_path = os.path.join(folder, "info.json")
        if os.path.exists(info_path):
            try:
                with open(info_path, "r", encoding="utf-8") as f:
                    info = json.load(f)
                acc.email      = info.get("email", "")
                acc.password   = info.get("password", "")
                acc.created_at = info.get("created_at", "")
            except Exception:
                pass
        mgr = SessionManager(
            session_file=os.path.join(folder, "session_state.json"))
        if mgr.exists():
            meta = mgr.metadata()
            if meta:
                acc.session_exists   = True
                acc.session_saved_at = meta.get("saved_at")
                acc.cookie_count     = meta.get("cookie_count", 0)
        return acc

    def get_by_slot(self, slot: str) -> Optional[AccountInfo]:
        folder = os.path.join(self._base, slot)
        if os.path.isdir(folder):
            return self._load_one(slot, folder)
        return None

    def get_by_email(self, email: str) -> Optional[AccountInfo]:
        for acc in self.all():
            if acc.email.lower() == email.lower():
                return acc
        return None

    def count(self) -> int:
        return len(self.all())

    def count_logged(self) -> int:
        return sum(1 for a in self.all() if a.session_exists)

    # ── Write ────────────────────────────────────────────────────

    def add(self, email: str, password: str = "") -> Optional[AccountInfo]:
        if self.get_by_email(email):
            return None
        slot   = self._next_slot()
        folder = os.path.join(self._base, slot)
        os.makedirs(folder, exist_ok=True)
        info = {"email": email, "password": password,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        with open(os.path.join(folder, "info.json"), "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2, ensure_ascii=False)
        self._notify()
        return self._load_one(slot, folder)

    def update(self, slot: str, email: str = None, password: str = None) -> bool:
        info_path = os.path.join(self._base, slot, "info.json")
        if not os.path.exists(info_path):
            return False
        try:
            with open(info_path, "r", encoding="utf-8") as f:
                info = json.load(f)
            if email    is not None: info["email"]    = email
            if password is not None: info["password"] = password
            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(info, f, indent=2, ensure_ascii=False)
            self._notify()
            return True
        except Exception:
            return False

    def delete(self, slot: str) -> bool:
        folder = os.path.join(self._base, slot)
        if not os.path.isdir(folder):
            return False
        shutil.rmtree(folder, ignore_errors=True)
        self._notify()
        return True

    def delete_all(self):
        for acc in self.all():
            shutil.rmtree(acc.folder, ignore_errors=True)
        self._notify()

    def clear_session(self, slot: str):
        """Logout: xóa session_state.json của account."""
        folder = os.path.join(self._base, slot)
        SessionManager(
            session_file=os.path.join(folder, "session_state.json")
        ).clear()
        self._notify()

    def get_session_manager(self, slot: str) -> SessionManager:
        """Trả SessionManager cho account — LoginService dùng để save cookies."""
        folder = os.path.join(self._base, slot)
        return SessionManager(
            session_file=os.path.join(folder, "session_state.json"))

    def import_from_txt(self, path: str) -> int:
        added = 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    parts = line.split("|")

                    email = parts[0].strip()
                    pwd = parts[1].strip() if len(parts) > 1 else ""
                    token = parts[2].strip() if len(parts) > 2 else ""

                    # nếu cần lưu token thì sửa hàm add
                    if email and self.add(email, pwd):
                        added += 1

        except OSError:
            pass

        return added

    def export_to_txt(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            for acc in self.all():
                f.write(f"{acc.email}:{acc.password}\n")

    def _next_slot(self) -> str:
        existing = set()
        try:
            for name in os.listdir(self._base):
                m = re.match(r"^account_(\d+)$", name)
                if m:
                    existing.add(int(m.group(1)))
        except OSError:
            pass
        n = 1
        while n in existing:
            n += 1
        return f"account_{n:02d}"