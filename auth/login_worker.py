"""
auth/login_worker.py

Chỉ mở Chrome để người dùng đăng nhập.
KHÔNG tự động lưu session.
"""

import logging
from PySide6.QtCore import QThread, Signal
from auth.chrome_launcher import ChromeLauncher

logger = logging.getLogger(__name__)

LOGIN_URL = "https://accounts.x.ai/sign-in?redirect=grok-com&email=true"


class LoginWorker(QThread):

    log = Signal(str)
    chrome_ready = Signal(str, int)
    failed = Signal(str, str)

    def __init__(self, slot: str, chrome_path: str = None):
        super().__init__()
        self.slot = slot
        self._chrome_path = chrome_path
        self._launcher = None

    def run(self):

        slot = self.slot

        try:

            self.log.emit(f"[{slot}] 🌐 Đang mở trang đăng nhập...")

            launcher = ChromeLauncher(slot, chrome_path=self._chrome_path)
            self._launcher = launcher

            # mở trực tiếp login page
            port = launcher.open(LOGIN_URL)

            self.log.emit(f"[{slot}] ✅ Chrome sẵn sàng — port {port}")
            self.log.emit(f"[{slot}] 🔐 Hãy đăng nhập Grok trong cửa sổ Chrome")
            self.log.emit(f"[{slot}] 👉 Sau khi đăng nhập → nhấn [💾 Lưu Session]")

            self.chrome_ready.emit(slot, port)

        except Exception as e:

            msg = str(e)

            self.log.emit(f"[{slot}] ❌ Mở Chrome thất bại: {msg}")
            self.failed.emit(slot, msg)
