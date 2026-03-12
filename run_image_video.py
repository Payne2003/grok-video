import subprocess, time, os, requests, json, ctypes, ctypes.wintypes
from playwright.sync_api import sync_playwright

# ═══════════════════════════════════════════
CHROME_PATH   = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
USER_DATA     = r"D:\chrome-debug-profile"
SESSION_PATH  = r"D:\grok-video-tool\auth\session_state.json"
DEBUG_URL     = "http://127.0.0.1:9222/json"
OUTPUT_FOLDER = r"D:\grok-video-tool\outputs"

PROMPT     = "make the animal move and run in the forest"
IMAGE_PATH = r"assets\images\cat.jpg"
# ═══════════════════════════════════════════


def hide_all_chrome_windows():
    """Ẩn toàn bộ cửa sổ Chrome khỏi màn hình bằng WinAPI."""
    try:
        SW_HIDE = 0
        EnumWindows     = ctypes.windll.user32.EnumWindows
        ShowWindow      = ctypes.windll.user32.ShowWindow
        GetWindowTextW  = ctypes.windll.user32.GetWindowTextW
        GetWindowTextLenW = ctypes.windll.user32.GetWindowTextLengthW
        IsWindowVisible = ctypes.windll.user32.IsWindowVisible
        WNDENUMPROC     = ctypes.WINFUNCTYPE(ctypes.c_bool,
                                             ctypes.wintypes.HWND,
                                             ctypes.wintypes.LPARAM)
        def callback(hwnd, _):
            if not IsWindowVisible(hwnd):
                return True
            length = GetWindowTextLenW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            if "Chrome" in title or "Grok" in title or "grok" in title:
                ShowWindow(hwnd, SW_HIDE)
            return True
        EnumWindows(WNDENUMPROC(callback), 0)
    except Exception as e:
        print(f"[WARN] hide_windows: {e}")


def start_chrome():
    """Khởi động Chrome ẩn hoàn toàn — không hiện trên màn hình."""
    try:
        requests.get(DEBUG_URL, timeout=2)
        print("[TOOL] Chrome đang chạy sẵn")
        hide_all_chrome_windows()
        return
    except:
        pass

    print("[TOOL] Khởi động Chrome ẩn...")

    # STARTUPINFO để Chrome không hiện cửa sổ ngay từ đầu
    si = subprocess.STARTUPINFO()
    si.dwFlags    = subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0   # SW_HIDE = 0

    subprocess.Popen(
        [
            CHROME_PATH,
            "--remote-debugging-port=9222",
            f"--user-data-dir={USER_DATA}",
            "--window-size=1280,800",
            "--window-position=-32000,-32000",  # đẩy ra ngoài màn hình
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
        ],
        startupinfo=si,
        creationflags=subprocess.CREATE_NO_WINDOW,  # Windows: không tạo console
    )

    # Chờ Chrome sẵn sàng
    for i in range(20):
        try:
            requests.get(DEBUG_URL, timeout=2)
            print("[TOOL] Chrome sẵn sàng (ẩn)")
            # Ẩn thêm lần nữa phòng trường hợp cửa sổ kịp hiện
            time.sleep(1)
            hide_all_chrome_windows()
            return
        except:
            time.sleep(1)
    raise RuntimeError("Chrome không khởi động được")


def wait_cloudflare(page, max_sec=120):
    """
    Chờ Cloudflare tự pass — vì Chrome thật với profile cũ
    thường tự qua mà không cần click.
    Nếu vẫn bị chặn sau 10s, hiện cửa sổ Chrome để user click.
    """
    for i in range(max_sec):
        c = page.content().lower()
        if "verify you are human" not in c and "performing security" not in c:
            if i > 0: print()
            print("[TOOL] ✅ Qua Cloudflare")
            return

        if i == 10:
            # Sau 10s vẫn bị chặn → hiện Chrome để user xử lý
            print("\n[TOOL] Cloudflare cần xác minh — hiện Chrome...")
            _show_chrome_window()
            print("  → Click 'Verify you are human' trong Chrome")
            print("  → Chrome sẽ tự ẩn lại sau khi xong")

        if i > 10:
            # Kiểm tra đã qua chưa
            c = page.content().lower()
            if "verify you are human" not in c:
                print()
                print("[TOOL] ✅ Qua Cloudflare!")
                hide_all_chrome_windows()  # ẩn lại ngay
                return

        print(f"\r  Cloudflare... {i+1}s", end="", flush=True)
        time.sleep(1)

    raise RuntimeError("Timeout Cloudflare")


def _show_chrome_window():
    """Hiện lại cửa sổ Chrome (dùng khi cần user tương tác)."""
    try:
        SW_RESTORE = 9
        SW_SHOW    = 5
        EnumWindows    = ctypes.windll.user32.EnumWindows
        ShowWindow     = ctypes.windll.user32.ShowWindow
        SetForegroundWindow = ctypes.windll.user32.SetForegroundWindow
        GetWindowTextW = ctypes.windll.user32.GetWindowTextW
        GetWindowTextLenW = ctypes.windll.user32.GetWindowTextLengthW
        WNDENUMPROC    = ctypes.WINFUNCTYPE(ctypes.c_bool,
                                            ctypes.wintypes.HWND,
                                            ctypes.wintypes.LPARAM)
        # Đưa Chrome về đúng vị trí trên màn hình
        MoveWindow = ctypes.windll.user32.MoveWindow
        found = []
        def callback(hwnd, _):
            length = GetWindowTextLenW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            GetWindowTextW(hwnd, buf, length + 1)
            if "Chrome" in buf.value or "Grok" in buf.value:
                found.append(hwnd)
            return True
        EnumWindows(WNDENUMPROC(callback), 0)
        for hwnd in found:
            MoveWindow(hwnd, 100, 100, 1000, 700, True)
            ShowWindow(hwnd, SW_RESTORE)
            SetForegroundWindow(hwnd)
    except Exception as e:
        print(f"[WARN] show_window: {e}")


def inject_session_cookies(context):
    if not os.path.exists(SESSION_PATH):
        print("[WARN] Không có session — chạy save_session.py trước")
        return False
    with open(SESSION_PATH) as f:
        data = json.load(f)
    cookies = [c for c in data.get("cookies", [])
               if "grok" in c.get("domain", "") or "x.ai" in c.get("domain", "")]
    if cookies:
        context.add_cookies(cookies)
        print(f"[TOOL] ✅ Nạp {len(cookies)} cookies")
    return bool(cookies)


def find_and_fill_prompt(page, prompt):
    for sel in ["textarea", "div[contenteditable='true']",
                "div[contenteditable='plaintext-only']", "div[role='textbox']",
                "[placeholder*='prompt' i]", "[placeholder*='Nhập' i]"]:
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
                print(f"[TOOL] ✅ Nhập prompt qua: {sel}")
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
                print(f"[TOOL] ✅ Click: {sel}")
                return True
        except:
            continue
    return False


def is_video_url(url, ct):
    if "imagine-public" in url or "share-video" in url:
        return False
    if "image/" in ct or "text/" in ct or "application/json" in ct:
        return False
    if "assets.grok.com" in url:
        if "video/" in ct:
            return True
        if "application/octet-stream" in ct and any(x in url for x in [".mp4", ".webm"]):
            return True
    return False


def download_with_cookies(url, save_path, cookies_dict):
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
    print(f"[TOOL] Content-Type: {ct} | {r.headers.get('content-length','?')} bytes")

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    downloaded = 0
    with open(save_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                print(f"\r  ⬇️  {downloaded // 1024} KB", end="", flush=True)
    print()
    return downloaded


def run_generation(prompt, image_path):
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Không tìm thấy ảnh: {image_path}")

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    start_chrome()  # Chrome ẩn hoàn toàn
    print("[TOOL] Kết nối Chrome...")

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        inject_session_cookies(context)
        page = context.pages[0] if context.pages else context.new_page()

        # Bắt video URL từ network ngay từ đầu
        captured = {"url": None, "cookies": None}

        def on_response(resp):
            try:
                url = resp.url
                ct  = resp.headers.get("content-type", "")
                if is_video_url(url, ct):
                    print(f"\n[NET] ✅ Bắt được: {url[:90]}")
                    captured["url"]     = url
                    captured["cookies"] = {c["name"]: c["value"]
                                           for c in page.context.cookies()}
            except:
                pass

        page.on("response", on_response)

        print("[TOOL] Mở grok.com/imagine (ẩn)...")
        try:
            page.goto("https://grok.com/imagine", wait_until="load", timeout=60000)
        except Exception as e:
            print(f"[WARN] {e}")

        time.sleep(3)
        hide_all_chrome_windows()   # ẩn ngay sau khi load
        wait_cloudflare(page)       # tự qua hoặc hiện lên nếu cần click
        hide_all_chrome_windows()   # ẩn lại sau Cloudflare
        print(f"[TOOL] URL: {page.url}")

        if "login" in page.url or "signin" in page.url:
            raise RuntimeError("Chưa đăng nhập! Chạy save_session.py trước.")

        # Upload ảnh
        print("[TOOL] Upload ảnh...")
        upload = page.wait_for_selector("input[type=file]", state="attached", timeout=20000)
        upload.set_input_files(image_path)
        print("[TOOL] ✅ Upload OK")
        time.sleep(3)

        # Nhập prompt
        print("[TOOL] Nhập prompt...")
        if not find_and_fill_prompt(page, prompt):
            raise RuntimeError("Không tìm thấy ô nhập prompt!")
        time.sleep(1)

        # Click Gửi
        print("[TOOL] Click Gửi...")
        if not click_submit(page):
            raise RuntimeError("Không tìm thấy nút Gửi!")

        # Chờ URL video được bắt
        print("[TOOL] Đang tạo video (tối đa 180s)...")
        for i in range(180):
            time.sleep(1)
            print(f"\r  ⏳ {i+1}s / 180s", end="", flush=True)

            if captured["url"]:
                print(f"\n[TOOL] ✅ Bắt được URL sau {i+1}s!")
                break

            try:
                btn = page.query_selector("button[aria-label='Download']")
                if btn and btn.is_visible():
                    btn.hover()
                    time.sleep(2)
                    if captured["url"]:
                        break
            except:
                pass

        print()
        try: page.screenshot(timeout=5000, path="result.png")
        except: pass

        if not captured["url"]:
            raise RuntimeError("Không bắt được URL video! Xem result.png")

        # Tải video
        video_url = captured["url"]
        cookies   = captured["cookies"] or {c["name"]: c["value"]
                                            for c in page.context.cookies()}
        ts        = int(time.time())
        ext       = "webm" if ".webm" in video_url else "mp4"
        save_path = os.path.join(OUTPUT_FOLDER, f"video_{ts}.{ext}")

        print(f"[TOOL] Tải: {video_url[:80]}...")
        print(f"[TOOL] Lưu: {save_path}")
        size = download_with_cookies(video_url, save_path, cookies)

        if size < 10000:
            raise RuntimeError(f"File quá nhỏ ({size} bytes) — lỗi xác thực")

        print()
        print("=" * 50)
        print("  ✅  HOÀN THÀNH!")
        print(f"  📁  {save_path}")
        print(f"  📦  {size // 1024} KB")
        print("=" * 50)


if __name__ == "__main__":
    run_generation(PROMPT, IMAGE_PATH)