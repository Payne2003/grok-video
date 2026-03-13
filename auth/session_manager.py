"""auth/session_manager.py — Handles browser session persistence."""

import json, logging, os, shutil, tempfile, threading
from datetime import datetime, timezone
from typing import Optional
from auth.exceptions import SessionCorruptedError, SessionSaveError

logger = logging.getLogger(__name__)
_REQUIRED_COOKIE_FIELDS = frozenset({"name", "value", "domain", "path"})
_SESSION_VERSION = 1


class SessionManager:
    def __init__(self, session_file: Optional[str] = None) -> None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self._file = session_file or os.path.join(base_dir, "session_state.json")
        self._backup = self._file + ".bak"
        self._lock = threading.Lock()

    def save(self, cookies: list[dict]) -> None:

        if not cookies:
            raise ValueError("Cannot save an empty cookie list.")

        validated = _validate_cookies(cookies)

        payload = {
            "version": _SESSION_VERSION,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "cookie_count": len(validated),
            "cookies": validated,
        }

        with self._lock:
            self._atomic_write(payload)

        logger.info(
            "[SessionManager] Saved %d cookies → %s",
            len(validated),
            self._file
        )

    def load(self) -> Optional[list[dict]]:
        with self._lock:
            if not os.path.exists(self._file):
                return None
            raw = self._safe_read(self._file)
        if raw is None:
            with self._lock:
                raw = self._safe_read(self._backup)
            if raw is None:
                raise SessionCorruptedError("Session file corrupted and no backup found.")
        cookies = raw.get("cookies")
        if not isinstance(cookies, list) or not cookies:
            raise SessionCorruptedError("Session payload contains no cookies.")
        return _validate_cookies(cookies)

    def clear(self) -> None:
        with self._lock:
            for path in (self._file, self._backup):
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError as e:
                        logger.warning("Cannot remove %s: %s", path, e)

    def exists(self) -> bool:
        return os.path.exists(self._file)

    def metadata(self) -> Optional[dict]:
        with self._lock:
            raw = self._safe_read(self._file)
        if raw is None:
            return None
        return {
            "version": raw.get("version"),
            "saved_at": raw.get("saved_at"),
            "cookie_count": raw.get("cookie_count"),
        }

    def _atomic_write(self, payload: dict) -> None:
        dir_name = os.path.dirname(self._file) or "."
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=dir_name,
                    delete=False, suffix=".tmp"
            ) as tmp:
                json.dump(payload, tmp, indent=2, ensure_ascii=False)
                tmp_path = tmp.name
            os.replace(tmp_path, self._file)
        except (OSError, TypeError) as e:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except:
                    pass
            raise SessionSaveError(f"Failed to write session: {e}") from e

    def _backup_existing(self) -> None:
        if os.path.exists(self._file):
            try:
                shutil.copy2(self._file, self._backup)
            except OSError as e:
                logger.warning("Backup failed: %s", e)

    @staticmethod
    def _safe_read(path: str) -> Optional[dict]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None


def _validate_cookies(cookies: list[dict]) -> list[dict]:
    for idx, cookie in enumerate(cookies):
        if not isinstance(cookie, dict):
            raise ValueError(f"Cookie[{idx}] is not a dict.")
        missing = _REQUIRED_COOKIE_FIELDS - cookie.keys()
        if missing:
            raise ValueError(f"Cookie[{idx}] missing fields: {sorted(missing)}")
    return cookies
