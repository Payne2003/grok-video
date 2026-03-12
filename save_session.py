"""
save_session.py — Đăng nhập và lưu session vào accounts/

Cách dùng:
    python save_session.py
    python save_session.py -a account_01
    python save_session.py --list
"""

import argparse, os, sys, subprocess, time, requests, shutil, json
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from auth.exceptions import BrowserNotReadyError, LoginTimeoutError
from auth.login_service import LoginService
from auth.session_manager import SessionManager


CHROME_PATH     = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
ACCOUNTS_FOLDER = r"D:\grok-video-tool\accounts"
PROFILES_BASE   = r"D:\chrome-profiles"
BASE_PORT       = 9300


# ════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════
import json

def get_user_id_from_cookies(cookies):
    for c in cookies:
        if c.get("name") == "x-userid":
            return c.get("value")
    return None


def is_duplicate_session(cookies):

    new_id = get_user_id_from_cookies(cookies)

    if not new_id:
        print("[AUTH] ⚠️ Không tìm thấy x-userid")
        return False

    print(f"[AUTH] USER ID: {new_id}")

    if not os.path.exists(ACCOUNTS_FOLDER):
        return False

    for acc in os.listdir(ACCOUNTS_FOLDER):

        session_file = os.path.join(
            ACCOUNTS_FOLDER, acc, "session_state.json"
        )

        if not os.path.exists(session_file):
            continue

        try:
            with open(session_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            old_id = get_user_id_from_cookies(data.get("cookies", []))

            if old_id == new_id:
                print(f"[AUTH] ⚠️ Session trùng với account: {acc}")
                return True

        except:
            continue

    return False



def get_next_account_name():

    os.makedirs(ACCOUNTS_FOLDER, exist_ok=True)

    existing = sorted([
        d for d in os.listdir(ACCOUNTS_FOLDER)
        if os.path.isdir(os.path.join(ACCOUNTS_FOLDER, d))
        and os.path.exists(os.path.join(ACCOUNTS_FOLDER, d, "session_state.json"))
    ])

    if not existing:
        return "account_01"

    try:
        num = int(existing[-1].split("_")[-1]) + 1
        return f"account_{num:02d}"
    except:
        return f"account_{len(existing)+1:02d}"


def start_chrome_for_login(port, profile_dir):

    debug_url = f"http://127.0.0.1:{port}/json"

    try:
        requests.get(debug_url, timeout=2)
        print(f"[AUTH] Chrome debug port {port} đang chạy")
        return
    except:
        raise RuntimeError(
f"""
[AUTH] Chrome debug chưa chạy

Hãy chạy trước:

python open_grok_login.py

(port {port})
"""
        )


def cleanup_failed_account(account_dir, profile_dir, account_name):

    if os.path.exists(account_dir):

        try:
            shutil.rmtree(account_dir)
            print(f"[AUTH] 🧹 Đã xoá account lỗi: {account_name}")
        except:
            pass


# ════════════════════════════════════════════════════════════════
# MAIN FLOW
# ════════════════════════════════════════════════════════════════

def save_session_for_account(account_name):

    account_dir  = os.path.join(ACCOUNTS_FOLDER, account_name)
    session_file = os.path.join(account_dir, "session_state.json")

    profile_dir  = os.path.join(PROFILES_BASE, "grok_login")

    port = BASE_PORT


    print(f"""
╔══════════════════════════════════════════════╗
║         LƯU SESSION GROK                    ║
╠══════════════════════════════════════════════╣
║  Account : {account_name:<32}║
║  Port    : {port:<32}║
╚══════════════════════════════════════════════╝
""")


    success = False

    try:

        start_chrome_for_login(port, profile_dir)

        with sync_playwright() as p:

            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")

            context = browser.contexts[0] if browser.contexts else browser.new_context()

            page = context.pages[0] if context.pages else context.new_page()

            print("[AUTH] Mở grok.com...")

            try:
                page.goto("https://grok.com", timeout=30000)
            except:
                pass

            time.sleep(3)


            tmp_session = os.path.join(profile_dir, "_tmp_session.json")

            session_mgr = SessionManager(session_file=tmp_session)


            login_svc = LoginService(
                page=page,
                session_manager=session_mgr,
                log_callback=lambda x: print("[AUTH]", x),
                timeout=300,
                poll_interval=3
            )


            try:
                login_svc.ensure_logged_in()
            except LoginTimeoutError:
                print("[AUTH] ❌ Timeout login")
                return False
            except BrowserNotReadyError as e:
                print("[AUTH] ❌ Browser lỗi:", e)
                return False


            # ─────────────────────────────
            # Lấy user info từ API
            # ─────────────────────────────

            user_info = page.evaluate("""
            async () => {
                try {
                    const r = await fetch("/rest/user", {credentials:"include"});
                    return await r.json();
                } catch {
                    return null;
                }
            }
            """)

            print("[AUTH] USER INFO:", user_info)

            user_key = None

            if user_info:

                user_key = user_info.get("id") or user_info.get("username")


            print("[AUTH] USER KEY:", user_key)

            # ─────────────────────────────
            # Kiểm tra session
            # ─────────────────────────────

            if not session_mgr.exists():

                print("[AUTH] ❌ Session không tồn tại")

                return False


            cookies = session_mgr.load()
            # kiểm tra account trùng
            if is_duplicate_session(cookies):
                    print("[AUTH] Session đã tồn tại → bỏ qua")
                    return False


            if not cookies or len(cookies) < 3:

                print("[AUTH] ❌ Session cookie lỗi")

                return False


            grok_cookies = [
                c for c in cookies
                if "grok" in c.get("domain","") or "x.ai" in c.get("domain","")
            ]

            if not grok_cookies:

                print("[AUTH] ❌ Không có cookie Grok")

                return False


            # ─────────────────────────────
            # Tạo account
            # ─────────────────────────────

            os.makedirs(account_dir, exist_ok=True)

            shutil.copy2(tmp_session, session_file)


            if user_key:

                with open(os.path.join(account_dir,"user_key.txt"),"w",encoding="utf-8") as f:

                    f.write(user_key)


            success = True


            print(f"""
[AUTH] ╔══════════════════════════════════╗
[AUTH] ║   SESSION LƯU THÀNH CÔNG        ║
[AUTH] ╠══════════════════════════════════╣
[AUTH] ║  Account : {account_name:<20}║
[AUTH] ║  UserKey : {user_key:<20}║
[AUTH] ║  Cookies : {len(cookies):<20}║
[AUTH] ╚══════════════════════════════════╝
""")


            return True


    except Exception as e:

        print("[AUTH] ❌ Lỗi:", e)

        return False


    finally:

        if not success:

            cleanup_failed_account(account_dir, profile_dir, account_name)


        tmp = os.path.join(profile_dir,"_tmp_session.json")

        if os.path.exists(tmp):

            try:
                os.remove(tmp)
            except:
                pass


# ════════════════════════════════════════════════════════════════
# LIST ACCOUNTS
# ════════════════════════════════════════════════════════════════

def list_accounts():

    if not os.path.exists(ACCOUNTS_FOLDER):

        print("[AUTH] Chưa có account")

        return


    accounts = os.listdir(ACCOUNTS_FOLDER)


    print("\nAccounts:")

    for acc in accounts:

        key = os.path.join(ACCOUNTS_FOLDER,acc,"user_key.txt")

        if os.path.exists(key):

            with open(key) as f:

                print("  ",acc,"|",f.read().strip())

        else:

            print("  ",acc,"| unknown")


# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument("-a","--account")

    parser.add_argument("-l","--list",action="store_true")

    args = parser.parse_args()


    if args.list:

        list_accounts()

        sys.exit(0)


    name = args.account or get_next_account_name()

    ok = save_session_for_account(name)

    sys.exit(0 if ok else 1)
