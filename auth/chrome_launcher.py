"""
auth/chrome_launcher.py
Mở Chrome debug port cho từng account
"""

import os
import socket
import subprocess
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

_BASE_PORT = 9300

_PROFILES_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "profiles"
)


def find_chrome():

    user = os.environ.get("USERNAME", "")
    extra = rf"C:\Users\{user}\AppData\Local\Google\Chrome\Application\chrome.exe"

    for p in _CHROME_CANDIDATES + [extra]:
        if os.path.exists(p):
            return p

    raise FileNotFoundError("Không tìm thấy Chrome")


def slot_to_port(slot: str):

    try:
        return _BASE_PORT + int(slot.split("_")[-1]) - 1
    except Exception:
        return _BASE_PORT


def slot_to_profile(slot: str):

    return os.path.join(_PROFILES_ROOT, slot)


def is_port_open(port: int, timeout: float = 1.0):

    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


class ChromeLauncher:

    def __init__(self, slot: str, chrome_path: str = None):

        self.slot = slot
        self.port = slot_to_port(slot)
        self.profile_dir = slot_to_profile(slot)

        self._chrome = chrome_path or find_chrome()
        self._proc: Optional[subprocess.Popen] = None

    def open(self, url: str = "https://grok.com", wait: float = 8.0) -> int:

        os.makedirs(self.profile_dir, exist_ok=True)

        # nếu port đã mở → mở tab mới
        if is_port_open(self.port):

            logger.info("[%s] port %d đã mở → mở tab login", self.slot, self.port)

            try:
                import urllib.request

                req = urllib.request.Request(
                    f"http://127.0.0.1:{self.port}/json/new?{url}",
                    method="PUT"
                )

                urllib.request.urlopen(req)

            except Exception:
                pass

            return self.port

        cmd = [
            self._chrome,
            f"--remote-debugging-port={self.port}",
            f"--user-data-dir={self.profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-sync",
            "--start-maximized",
            url,
        ]

        logger.info("[%s] Mở Chrome port %d", self.slot, self.port)

        self._proc = subprocess.Popen(cmd)

        deadline = time.monotonic() + wait

        while time.monotonic() < deadline:
            if is_port_open(self.port):
                return self.port
            time.sleep(0.5)

        raise TimeoutError(f"Chrome không bind port {self.port} sau {wait}s")

    @property
    def cdp_url(self):

        return f"http://127.0.0.1:{self.port}"
