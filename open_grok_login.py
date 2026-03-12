import subprocess
import os

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

PORT = 9300

PROFILE_DIR = r"D:\chrome-profiles\grok_login"


def main():

    os.makedirs(PROFILE_DIR, exist_ok=True)

    print("[LOGIN] Mở Chrome...")

    subprocess.Popen([
        CHROME_PATH,

        f"--remote-debugging-port={PORT}",
        f"--user-data-dir={PROFILE_DIR}",

        "--no-first-run",
        "--no-default-browser-check",
        "--disable-sync",
        "--start-maximized",

        "https://grok.com"
    ])


if __name__ == "__main__":
    main()
