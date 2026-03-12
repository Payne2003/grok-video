"""
run_batch.py — Smart queue: mỗi account xử lý 3 scene song song,
                hễ xong 1 → kéo scene mới từ queue vào ngay.
                Nhiều account → chia scene theo Divide & Conquer.
"""
import os, json, time, logging
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from queue import Queue, Empty
from threading import Lock
import sys

logging.getLogger("asyncio").setLevel(logging.CRITICAL)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth.session_manager import SessionManager
from auth.exceptions import SessionCorruptedError
from worker import run_scene

# ═══════════════════════════════════════════════════════════
SCENES_FOLDER   = r"scenes"
OUTPUT_FOLDER   = r"D:\grok-video-tool\outputs"
ACCOUNTS_FOLDER = r"D:\grok-video-tool\accounts"
PROFILES_BASE   = r"D:\chrome-profiles"
SOURCE_PROFILE  = r"D:\chrome-debug-profile"   # profile Chrome gốc dùng để clone

BASE_PORT       = 9222
SLOTS_PER_ACC   = 1     # Grok xử lý 1 video/lần per account → giữ 1 slot
MAX_RETRIES     = 3     # Số lần retry khi scene thất bại
RETRY_DELAY     = 10    # Giây chờ trước khi retry
# ═══════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════
#  SCAN SCENES
# ════════════════════════════════════════════════════════════

def scan_scenes():
    scenes = []
    if not os.path.exists(SCENES_FOLDER):
        raise FileNotFoundError(f"Không tìm thấy: {SCENES_FOLDER}")

    for name in sorted(os.listdir(SCENES_FOLDER)):
        d = os.path.join(SCENES_FOLDER, name)
        if not os.path.isdir(d): continue

        img = None
        for ext in ["jpg","jpeg","png","webp"]:
            for fn in [f"image.{ext}", f"{name}.{ext}"]:
                p = os.path.join(d, fn)
                if os.path.exists(p): img = p; break
            if img: break
        if not img:
            for f in os.listdir(d):
                if f.lower().endswith((".jpg",".jpeg",".png",".webp")):
                    img = os.path.join(d, f); break

        prompt_f = os.path.join(d, "prompt.txt")
        if not img or not os.path.exists(prompt_f): continue
        prompt = open(prompt_f, encoding="utf-8").read().strip()
        if not prompt: continue

        scenes.append({"name": name, "image": img, "prompt": prompt})
        print(f"[SCAN] ✅ {name} | {prompt[:55]}")
    return scenes


# ════════════════════════════════════════════════════════════
#  LOAD ACCOUNTS
# ════════════════════════════════════════════════════════════

def load_accounts():
    """
    Mỗi account có SLOTS_PER_ACC slot, mỗi slot = port riêng + profile riêng.
    account_01: slot0→9222, slot1→9223, slot2→9224
    account_02: slot0→9225, slot1→9226, slot2→9227
    """
    def make_slots(name, port_start):
        return [
            {
                "port":        port_start + s,
                "profile_dir": os.path.join(PROFILES_BASE, f"{name}_slot{s}"),
            }
            for s in range(SLOTS_PER_ACC)
        ]

    accounts = []
    port_cursor = BASE_PORT

    if not os.path.exists(ACCOUNTS_FOLDER):
        default = r"D:\grok-video-tool\auth\session_state.json"
        if os.path.exists(default):
            slots = make_slots("account_01", port_cursor)
            accounts.append({
                "id":             "account_01",
                "session_path":   default,
                "source_profile": SOURCE_PROFILE,
                "slots":          slots,
            })
            ports = f"{slots[0]['port']}-{slots[-1]['port']}"
            print(f"[ACC] ✅ account_01 (default) | ports {ports}")
        return accounts

    for name in sorted(os.listdir(ACCOUNTS_FOLDER)):
        acc_dir = os.path.join(ACCOUNTS_FOLDER, name)
        sess    = os.path.join(acc_dir, "session_state.json")
        if not os.path.isdir(acc_dir): continue

        mgr = SessionManager(session_file=sess)
        if not mgr.exists():
            print(f"[ACC] ❌ {name} — chưa có session"); continue
        try:
            cookies = mgr.load()
            if not cookies: continue
        except SessionCorruptedError as e:
            print(f"[ACC] ❌ {name} — session lỗi: {e}"); continue

        slots  = make_slots(name, port_cursor)
        port_cursor += SLOTS_PER_ACC

        # Tất cả accounts dùng chung SOURCE_PROFILE làm base clone
        # (cookies riêng của từng account sẽ được inject qua Playwright)
        source_profile = SOURCE_PROFILE

        meta = mgr.metadata()
        accounts.append({
            "id":             name,
            "session_path":   sess,
            "source_profile": source_profile,
            "slots":          slots,
        })
        ports = f"{slots[0]['port']}-{slots[-1]['port']}"
        print(f"[ACC] ✅ {name} | {meta['cookie_count']} cookies | ports {ports}")

    return accounts


# ════════════════════════════════════════════════════════════
#  DIVIDE & CONQUER — chia scenes cho accounts
# ════════════════════════════════════════════════════════════

def divide_scenes(scenes: list, accounts: list) -> dict:
    """
    Chia scenes đều cho accounts theo Divide & Conquer.

    - scenes <= accounts : mỗi account nhận đúng 1 scene
    - scenes > accounts  : chia đệ quy, mỗi account nhận 1 chunk liên tục
                           (giữ tính locality — scenes liên quan gần nhau)

    Trả về: { account_id: [scene, ...] }
    """
    n_scenes = len(scenes)
    n_acc    = len(accounts)

    assignment = {acc["id"]: [] for acc in accounts}

    def _divide(scene_list, acc_list):
        if not scene_list or not acc_list:
            return
        if len(acc_list) == 1:
            # Base case: 1 account nhận tất cả scenes còn lại
            assignment[acc_list[0]["id"]].extend(scene_list)
            return
        # Chia đôi cả scenes lẫn accounts
        mid_s = len(scene_list) // 2
        mid_a = len(acc_list)   // 2
        _divide(scene_list[:mid_s], acc_list[:mid_a])
        _divide(scene_list[mid_s:], acc_list[mid_a:])

    if n_scenes <= n_acc:
        # 1 scene → 1 account, bỏ qua accounts thừa
        for i, scene in enumerate(scenes):
            assignment[accounts[i]["id"]].append(scene)
    else:
        _divide(scenes, accounts)

    # In kế hoạch phân phối
    print("\n[PLAN] Phân phối Divide & Conquer:")
    print(f"       {n_scenes} scenes → {n_acc} accounts")
    print("─" * 55)
    for acc in accounts:
        chunk = assignment[acc["id"]]
        names = [s["name"] for s in chunk]
        bar   = "█" * len(chunk)
        print(f"  {acc['id']:<20} [{bar:<15}] {len(chunk):>2} scenes: {', '.join(names[:4])}{'...' if len(names)>4 else ''}")
    print("─" * 55 + "\n")

    return assignment


# ════════════════════════════════════════════════════════════
#  RETRY WRAPPER
# ════════════════════════════════════════════════════════════

def run_scene_with_retry(scene, acc, slot):
    """Chạy scene với retry tự động khi thất bại."""
    last_result = None
    for attempt in range(1, MAX_RETRIES + 1):
        if attempt > 1:
            print(f"[RETRY] {scene['name']} lần {attempt}/{MAX_RETRIES} "
                  f"(lỗi: {last_result.get('error','?')[:60]}) → chờ {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)

        result = run_scene(
            scene_name     = scene["name"],
            image_path     = scene["image"],
            prompt         = scene["prompt"],
            output_folder  = OUTPUT_FOLDER,
            port           = slot["port"],
            user_data_dir  = slot["profile_dir"],
            session_path   = acc["session_path"],
            source_profile = acc["source_profile"],
        )

        if result["status"] == "success":
            if attempt > 1:
                print(f"[RETRY] ✅ {scene['name']} thành công ở lần {attempt}")
            return result

        last_result = result
        # Lỗi không thể retry (không có ảnh, không có prompt...)
        no_retry_errors = ["Không tìm thấy ảnh", "prompt", "FileNotFoundError"]
        if any(e in str(result.get("error","")) for e in no_retry_errors):
            print(f"[RETRY] ⛔ {scene['name']} lỗi không thể retry: {result['error']}")
            return result

    print(f"[RETRY] ❌ {scene['name']} thất bại sau {MAX_RETRIES} lần")
    return last_result


# ════════════════════════════════════════════════════════════
#  ACCOUNT WORKER — xử lý chunk của 1 account
#  Logic: 3 slot song song, hễ slot xong → kéo scene mới ngay
# ════════════════════════════════════════════════════════════

def run_account(acc: dict, scene_chunk: list, global_results: list,
                results_lock: Lock, print_lock: Lock,
                global_queue: Queue, total_scenes: int):
    """
    Mỗi slot dùng port riêng + profile riêng → không tranh nhau Chrome.
    Slot pool: round-robin khi nạp đầu, trả slot về pool khi xong.
    """
    acc_id = acc["id"]
    slots  = acc["slots"]   # [{"port": ..., "profile_dir": ...}, ...]

    def plog(msg):
        with print_lock:
            print(f"[{acc_id}] {msg}")

    local_q    = Queue()
    slot_pool  = Queue()   # các slot đang rảnh

    for s in scene_chunk:
        local_q.put(s)
    for slot in slots:
        slot_pool.put(slot)

    def next_scene():
        try:    return local_q.get_nowait()
        except Empty: pass
        try:    return global_queue.get_nowait()
        except Empty: return None

    plog(f"Bắt đầu | {len(scene_chunk)} scenes | {len(slots)} slots độc lập")

    completed = 0
    active: dict = {}   # future → (scene_name, slot)

    with ThreadPoolExecutor(max_workers=len(slots)) as pool:

        # Nạp đầy tất cả slots
        for _ in range(len(slots)):
            scene = next_scene()
            if scene is None: break
            slot = slot_pool.get()
            f = pool.submit(run_scene_with_retry, scene, acc, slot)
            active[f] = (scene["name"], slot)
            plog(f"🚀 [{scene['name']}] → port {slot['port']} (active={len(active)})")

        while active:
            done_f = next(as_completed(active))
            scene_name, slot = active.pop(done_f)
            completed += 1

            # Trả slot về pool
            slot_pool.put(slot)

            try:
                result = done_f.result()
            except Exception as e:
                result = {"scene": scene_name, "status": "error",
                          "output": None, "error": str(e)}

            with results_lock:
                global_results.append(result)
                done_total = len(global_results)

            icon = "✅" if result["status"] == "success" else "❌"
            plog(f"{icon} [{scene_name}] [{done_total}/{total_scenes}] port {slot['port']} "
                 f"{'→ ' + result['output'] if result.get('output') else result.get('error','')}")

            # Kéo scene mới vào slot vừa giải phóng
            next_s = next_scene()
            if next_s:
                free_slot = slot_pool.get()
                f = pool.submit(run_scene_with_retry, next_s, acc, free_slot)
                active[f] = (next_s["name"], free_slot)
                plog(f"🔄 [{next_s['name']}] → port {free_slot['port']} (active={len(active)})")

    plog(f"✅ Hoàn thành {completed} scenes")


# ════════════════════════════════════════════════════════════
#  ORCHESTRATOR
# ════════════════════════════════════════════════════════════

def run_batch():
    print("[BATCH] Quét scenes...")
    scenes   = scan_scenes()
    accounts = load_accounts()

    if not scenes:
        print("[BATCH] ❌ Không có scene nào!"); return
    if not accounts:
        print("[BATCH] ❌ Không có account nào!"); return

    n_s, n_a = len(scenes), len(accounts)

    print(f"""
╔══════════════════════════════════════════════╗
║        GROK BATCH VIDEO TOOL                ║
╠══════════════════════════════════════════════╣
║  Scenes   : {n_s:<32}║
║  Accounts : {n_a:<32}║
║  Slots/acc: {SLOTS_PER_ACC:<32}║
║  Max song song: {n_a * SLOTS_PER_ACC:<28}║
╚══════════════════════════════════════════════╝
""")

    # Phân phối D&C
    assignment = divide_scenes(scenes, accounts)

    # Global queue — scenes dư (overflow) để các account xong trước steal
    # Trong D&C thuần thì queue này rỗng, nhưng giữ để mở rộng sau
    global_queue  = Queue()
    global_results: list = []
    results_lock  = Lock()
    print_lock    = Lock()

    start_time = time.time()

    # Chạy mỗi account trong 1 thread riêng
    with ThreadPoolExecutor(max_workers=n_a) as acc_pool:
        acc_futures = []
        for acc in accounts:
            chunk = assignment[acc["id"]]
            if not chunk:
                continue
            f = acc_pool.submit(
                run_account,
                acc, chunk,
                global_results, results_lock, print_lock,
                global_queue, n_s,
            )
            acc_futures.append(f)

        for f in as_completed(acc_futures):
            try:
                f.result()
            except Exception as e:
                if "TargetClosedError" not in str(e):
                    print(f"[BATCH] ⚠️  Account lỗi: {e}")

    # Tổng kết
    elapsed = time.time() - start_time
    success = sum(1 for r in global_results if r["status"] == "success")
    failed  = len(global_results) - success

    print(f"""
╔══════════════════════════════════════════════╗
║              KẾT QUẢ BATCH                  ║
╠══════════════════════════════════════════════╣
║  ✅ Thành công : {success:<28}║
║  ❌ Thất bại   : {failed:<28}║
║  ⏱  Thời gian  : {f"{elapsed:.0f}s":<28}║
╚══════════════════════════════════════════════╝
""")

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    report = os.path.join(OUTPUT_FOLDER, "batch_report.json")
    with open(report, "w", encoding="utf-8") as f:
        json.dump({
            "total": n_s, "success": success, "failed": failed,
            "elapsed": f"{elapsed:.0f}s",
            "results": global_results,
        }, f, ensure_ascii=False, indent=2)
    print(f"[BATCH] Report: {report}")


if __name__ == "__main__":
    run_batch()