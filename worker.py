"""
worker.py — Mỗi worker chạy 1 Chrome riêng trên 1 port riêng.
Hỗ trợ 2 chế độ:
  - Text → Video : image_path=None, chỉ nhập prompt
  - Image → Video: image_path=str,  upload ảnh rồi nhập prompt
"""
import subprocess, time, os, requests, json, ctypes, ctypes.wintypes
from playwright.sync_api import sync_playwright

SESSION_PATH = r"D:\grok-video-tool\auth\session_state.json"


# ════════════════════════════════════════════════════════════════
#  WinAPI: ẩn/hiện Chrome theo PID
# ════════════════════════════════════════════════════════════════

def hide_chrome_by_pid(pid):
    if not pid: return
    try:
        SW_HIDE = 0
        EnumWindows              = ctypes.windll.user32.EnumWindows
        ShowWindow               = ctypes.windll.user32.ShowWindow
        IsWindowVisible          = ctypes.windll.user32.IsWindowVisible
        GetWindowThreadProcessId = ctypes.windll.user32.GetWindowThreadProcessId
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool,
                                         ctypes.wintypes.HWND,
                                         ctypes.wintypes.LPARAM)
        def cb(hwnd, _):
            if IsWindowVisible(hwnd):
                pid_out = ctypes.wintypes.DWORD()
                GetWindowThreadProcessId(hwnd, ctypes.byref(pid_out))
                if pid_out.value == pid:
                    ShowWindow(hwnd, SW_HIDE)
            return True
        EnumWindows(WNDENUMPROC(cb), 0)
    except:
        pass


def show_chrome_by_pid(pid):
    if not pid: return
    try:
        SW_RESTORE          = 9
        EnumWindows         = ctypes.windll.user32.EnumWindows
        ShowWindow          = ctypes.windll.user32.ShowWindow
        MoveWindow          = ctypes.windll.user32.MoveWindow
        SetForegroundWindow = ctypes.windll.user32.SetForegroundWindow
        GetWindowThreadProcessId = ctypes.windll.user32.GetWindowThreadProcessId
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool,
                                         ctypes.wintypes.HWND,
                                         ctypes.wintypes.LPARAM)
        def cb(hwnd, _):
            pid_out = ctypes.wintypes.DWORD()
            GetWindowThreadProcessId(hwnd, ctypes.byref(pid_out))
            if pid_out.value == pid:
                MoveWindow(hwnd, 100, 100, 1000, 700, True)
                ShowWindow(hwnd, SW_RESTORE)
                SetForegroundWindow(hwnd)
            return True
        EnumWindows(WNDENUMPROC(cb), 0)
    except:
        pass


# ════════════════════════════════════════════════════════════════
#  Clone profile & khởi động Chrome
# ════════════════════════════════════════════════════════════════

SOURCE_PROFILE = r"D:\chrome-debug-profile"


def clone_profile_if_needed(source, dest, log):
    import shutil
    if os.path.exists(dest):
        cookies_file = os.path.join(dest, "Default", "Cookies")
        if os.path.exists(cookies_file):
            log(f"Profile {os.path.basename(dest)} đã có — bỏ qua clone")
            return
        log(f"Profile {os.path.basename(dest)} thiếu Cookies — clone lại")
    else:
        log(f"Tạo profile mới: {os.path.basename(dest)}")

    if not source or not os.path.exists(source):
        log(f"Source profile không tồn tại → tạo profile trống")
        os.makedirs(os.path.join(dest, "Default"), exist_ok=True)
        return

    if os.path.exists(dest):
        shutil.rmtree(dest, ignore_errors=True)

    important = [
        "Default/Cookies", "Default/Cookies-journal", "Default/Local State",
        "Default/Preferences", "Default/Web Data", "Default/Login Data",
        "Default/Local Storage", "Default/Session Storage",
        "Default/IndexedDB", "Local State",
    ]
    for rel_path in important:
        src = os.path.join(source, rel_path)
        dst = os.path.join(dest,   rel_path)
        if os.path.exists(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            try:
                if os.path.isdir(src):
                    def ignore_locks(d, files): return [f for f in files if f == "LOCK"]
                    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=ignore_locks)
                else:
                    if os.path.basename(src) != "LOCK":
                        shutil.copy2(src, dst)
            except Exception as e:
                log(f"  WARN copy {rel_path}: {e}")
    log(f"✅ Clone profile xong → {dest}")


def start_chrome(port, user_data_dir, log, source_profile=None):
    debug_url = f"http://127.0.0.1:{port}/json"
    try:
        requests.get(debug_url, timeout=2)
        log(f"Chrome port {port} đã chạy sẵn")
        return None, None
    except:
        pass

    _src = source_profile or SOURCE_PROFILE
    clone_profile_if_needed(_src, user_data_dir, log)

    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    si = subprocess.STARTUPINFO()
    si.dwFlags     = subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0

    args = [
        chrome_path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--window-size=1280,800",
        "--window-position=-32000,-32000",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
    ]

    proc = subprocess.Popen(args, startupinfo=si,
                            creationflags=subprocess.CREATE_NO_WINDOW)

    for _ in range(30):
        try:
            requests.get(debug_url, timeout=2)
            log(f"Chrome port {port} sẵn sàng (pid={proc.pid})")
            time.sleep(1)
            hide_chrome_by_pid(proc.pid)
            return proc, proc.pid
        except:
            time.sleep(1)

    log(f"Chrome port {port} chưa lên sau 30s — thử restart...")
    try: proc.terminate(); time.sleep(2)
    except: pass

    proc2 = subprocess.Popen(args, startupinfo=si,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    for _ in range(20):
        try:
            requests.get(debug_url, timeout=2)
            log(f"Chrome port {port} sẵn sàng lần 2 (pid={proc2.pid})")
            time.sleep(1); hide_chrome_by_pid(proc2.pid)
            return proc2, proc2.pid
        except:
            time.sleep(1)

    raise RuntimeError(f"Chrome port {port} không khởi động được sau 2 lần thử")


# ════════════════════════════════════════════════════════════════
#  Cloudflare
# ════════════════════════════════════════════════════════════════

def wait_cloudflare(page, chrome_pid, log, max_sec=120):
    cf_shown = False
    for i in range(max_sec):
        content = page.content().lower()
        is_cf   = ("verify you are human" in content
                   or "performing security" in content)
        if not is_cf:
            if i > 0: print()
            log("Qua Cloudflare ✅")
            if cf_shown:
                hide_chrome_by_pid(chrome_pid)
            return
        if i == 10 and not cf_shown:
            log("Cloudflare cần click — hiện Chrome lên")
            show_chrome_by_pid(chrome_pid)
            cf_shown = True
        time.sleep(1)
    raise RuntimeError("Timeout Cloudflare (120s)")


# ════════════════════════════════════════════════════════════════
#  Helpers
# ════════════════════════════════════════════════════════════════

def inject_cookies(context, log, session_path=None):
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from auth.session_manager import SessionManager
    from auth.exceptions import SessionCorruptedError

    _path = session_path or SESSION_PATH
    mgr   = SessionManager(session_file=_path)
    if not mgr.exists():
        log(f"WARN: Không có session: {_path}"); return False
    try:
        all_cookies = mgr.load()
    except SessionCorruptedError as e:
        log(f"WARN: Session bị hỏng: {e}"); return False
    if not all_cookies:
        log("WARN: Session rỗng"); return False

    cookies = [c for c in all_cookies
               if "grok" in c.get("domain", "") or "x.ai" in c.get("domain", "")]
    if cookies:
        context.add_cookies(cookies)
        meta     = mgr.metadata()
        saved_at = meta["saved_at"][:19] if meta else "?"
        log(f"✅ Nạp {len(cookies)} cookies (saved {saved_at})")
    return bool(cookies)


def find_and_fill_prompt(page, prompt):
    for sel in [
        "textarea",
        "div[contenteditable='true']",
        "div[contenteditable='plaintext-only']",
        "div[role='textbox']",
        "[placeholder*='prompt' i]",
        "[placeholder*='Nhập' i]",
        "[placeholder*='Describe' i]",
    ]:
        try:
            el = page.wait_for_selector(sel, state="visible", timeout=3000)
            if el:
                el.click(); time.sleep(0.3)
                ce = el.evaluate("e => e.getAttribute('contenteditable')")
                if ce is not None:
                    el.evaluate("e => e.innerText = ''")
                    el.type(prompt, delay=20)
                else:
                    el.fill(prompt)
                return True
        except:
            continue
    return False


def click_submit(page):
    for sel in ["button[aria-label='Gửi']", "button[aria-label='Send']",
                "button[type='submit']"]:
        try:
            btn = page.wait_for_selector(sel, state="visible", timeout=4000)
            if btn:
                btn.click()
                return True
        except:
            continue
    return False


def is_video_url(url, ct):
    if "imagine-public" in url or "share-video" in url: return False
    if "image/" in ct or "text/" in ct or "application/json" in ct: return False
    if "assets.grok.com" in url:
        if "video/" in ct: return True
        if "application/octet-stream" in ct and any(x in url for x in [".mp4", ".webm"]):
            return True
    return False


def get_video_url_from_dom(page):
    try:
        result = page.evaluate("""() => {
            const v = document.querySelector('video');
            if (v) {
                const src = v.src || v.currentSrc;
                if (src && src.startsWith('http') && !src.includes('imagine-public'))
                    return { url: src, via: 'video.src' };
                const s = v.querySelector('source');
                if (s && s.src && s.src.startsWith('http'))
                    return { url: s.src, via: 'source.src' };
            }
            for (const s of document.querySelectorAll('source')) {
                if (s.src && s.src.includes('assets.grok.com') && !s.src.includes('imagine-public'))
                    return { url: s.src, via: 'source tag' };
            }
            return null;
        }""")
        if result and result.get("url"):
            return result["url"], result.get("via", "dom")
    except:
        pass
    return None, None


def download_video(url, save_path, cookies_dict, log):
    auth_token = cookies_dict.get("auth_token") or cookies_dict.get("session") or ""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer":    "https://grok.com/",
        "Origin":     "https://grok.com",
        "Accept":     "video/webm,video/mp4,*/*",
    }
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    r = requests.get(url, headers=headers, cookies=cookies_dict,
                     stream=True, timeout=120)
    r.raise_for_status()
    ct = r.headers.get("content-type", "")
    log(f"Content-Type: {ct} | {r.headers.get('content-length','?')} bytes")

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    downloaded = 0
    with open(save_path, "wb") as f:
        for chunk in r.iter_content(65536):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                print(f"\r  ⬇️  {downloaded // 1024} KB", end="", flush=True)
    print()
    log(f"Tải xong: {os.path.basename(save_path)} ({downloaded//1024} KB)")
    return downloaded


# ════════════════════════════════════════════════════════════════
#  HÀM CHÍNH
# ════════════════════════════════════════════════════════════════

def run_scene(scene_name, image_path, prompt, output_folder,
              port, user_data_dir, session_path=None, source_profile=None):
    """
    Chạy 1 cảnh trên 1 Chrome riêng.

    image_path = None  →  Text → Video  (chỉ nhập prompt)
    image_path = str   →  Image → Video (upload ảnh + prompt)

    Trả về dict: { scene, status, output, error }
    """
    is_text_mode = (image_path is None or image_path == "")
    mode_label   = "Text→Video" if is_text_mode else "Image→Video"
    prefix       = f"[W{port - 9221}|{scene_name}|{mode_label}]"

    def log(msg): print(f"{prefix} {msg}")

    result     = {"scene": scene_name, "status": "error", "output": None, "error": None}
    proc       = None
    chrome_pid = None
    _session   = session_path or SESSION_PATH

    # Validate đầu vào
    if not prompt:
        result["error"] = "Prompt rỗng — cần nhập prompt"
        log(f"❌ {result['error']}")
        return result

    if not is_text_mode and not os.path.exists(image_path):
        result["error"] = f"Không tìm thấy ảnh: {image_path}"
        log(f"❌ {result['error']}")
        return result

    try:
        proc, chrome_pid = start_chrome(port, user_data_dir, log,
                                        source_profile=source_profile)

        log("Kết nối Chrome...")
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            context = (browser.contexts[0] if browser.contexts
                       else browser.new_context())
            inject_cookies(context, log, _session)
            page = (context.pages[0] if context.pages
                    else context.new_page())

            # Network listener bắt URL video
            captured = {"url": None, "ct": "", "cookies": None}

            def on_response(resp):
                try:
                    url = resp.url
                    ct  = resp.headers.get("content-type", "")
                    if is_video_url(url, ct):
                        log(f"✅ Video URL: {url[:70]} | ct={ct}")
                        captured["url"]     = url
                        captured["ct"]      = ct
                        captured["cookies"] = {c["name"]: c["value"]
                                               for c in page.context.cookies()}
                except:
                    pass

            page.on("response", on_response)

            log("Mở grok.com/imagine...")
            try:
                page.goto("https://grok.com/imagine",
                          wait_until="load", timeout=60000)
            except Exception as e:
                log(f"WARN goto: {e}")

            time.sleep(3)
            hide_chrome_by_pid(chrome_pid)
            wait_cloudflare(page, chrome_pid, log)
            hide_chrome_by_pid(chrome_pid)

            if "login" in page.url or "signin" in page.url:
                raise RuntimeError("Chưa đăng nhập! Chạy save_session.py trước.")

            # ── PHÂN NHÁNH: Image mode vs Text mode ──────────────

            if not is_text_mode:
                # ── IMAGE → VIDEO ─────────────────────────────────
                log(f"Upload: {os.path.basename(image_path)}")
                upload = page.wait_for_selector(
                    "input[type=file]", state="attached", timeout=20000
                )
                upload.set_input_files(image_path)
                log("Upload OK")
                time.sleep(3)

            else:
                # ── TEXT → VIDEO ──────────────────────────────────
                # Một số UI cần click nút "Text to video" / chọn tab
                # trước khi có thể nhập prompt thuần
                log("Text mode — tìm tab/nút Text to Video nếu có...")
                for tab_sel in [
                    "button:has-text('Text to video')",
                    "button:has-text('Text-to-video')",
                    "[aria-label*='Text to video' i]",
                    "button:has-text('Tạo từ văn bản')",
                ]:
                    try:
                        tab = page.query_selector(tab_sel)
                        if tab and tab.is_visible():
                            tab.click()
                            log(f"Đã click tab: {tab_sel}")
                            time.sleep(1)
                            break
                    except:
                        continue

            # ── NHẬP PROMPT (chung cả 2 mode) ────────────────────
            log(f"Prompt: {prompt[:60]}")
            if not find_and_fill_prompt(page, prompt):
                raise RuntimeError("Không tìm thấy ô nhập prompt!")
            time.sleep(1)

            # ── SUBMIT ────────────────────────────────────────────
            if not click_submit(page):
                raise RuntimeError("Không tìm thấy nút Gửi/Send!")
            log("Đang tạo video...")

            # ── CHỜ URL VIDEO ─────────────────────────────────────
            for i in range(180):
                time.sleep(1)
                print(f"\r{prefix} ⏳ {i+1}s / 180s", end="", flush=True)

                if captured["url"]:
                    print()
                    log(f"✅ Network listener bắt được sau {i+1}s!")
                    break

                if i % 5 == 4:
                    dom_url, via = get_video_url_from_dom(page)
                    if dom_url:
                        print()
                        log(f"✅ DOM fallback ({via}) sau {i+1}s: {dom_url[:70]}")
                        captured["url"]     = dom_url
                        captured["ct"]      = "video/mp4"
                        captured["cookies"] = {c["name"]: c["value"]
                                               for c in page.context.cookies()}
                        break

                if i % 10 == 9:
                    try:
                        btn = page.query_selector("button[aria-label='Download']")
                        if btn and btn.is_visible():
                            btn.hover(); time.sleep(1)
                    except:
                        pass
            else:
                dom_url, via = get_video_url_from_dom(page)
                if dom_url:
                    log(f"✅ DOM fallback cuối: {dom_url[:70]}")
                    captured["url"]     = dom_url
                    captured["ct"]      = "video/mp4"
                    captured["cookies"] = {c["name"]: c["value"]
                                           for c in page.context.cookies()}
                else:
                    try:
                        page.screenshot(
                            timeout=5000,
                            path=f"debug_{scene_name}_timeout.png"
                        )
                    except:
                        pass
                    raise RuntimeError("Timeout 180s — không bắt được URL video")

            # ── TẢI VIDEO ─────────────────────────────────────────
            os.makedirs(output_folder, exist_ok=True)
            real_ct = captured.get("ct", "")
            if "webm" in real_ct or ".webm" in captured["url"]:
                ext = "webm"
            else:
                ext = "mp4"

            save_path = os.path.join(output_folder, f"{scene_name}.{ext}")
            cookies   = captured["cookies"] or {
                c["name"]: c["value"] for c in page.context.cookies()
            }
            size = download_video(captured["url"], save_path, cookies, log)

            if size < 10000:
                raise RuntimeError(f"File quá nhỏ ({size} bytes) — lỗi xác thực")

            result["status"] = "success"
            result["output"] = save_path
            log(f"✅ XONG → {save_path}")

    except Exception as e:
        result["error"] = str(e)
        log(f"❌ LỖI: {e}")
    finally:
        if proc:
            try: proc.terminate()
            except: pass
        import sys; sys.stdout.flush()

    return result