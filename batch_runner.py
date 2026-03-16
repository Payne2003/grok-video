"""
batch_runner.py
───────────────
Cầu nối giữa logic batch (run_batch.py / worker.py) và UI controller.

Nhận:
  - scenes      : list[dict]  — từ GeneratorController.build_scenes()
  - accounts    : list[dict]  — từ load_accounts()
  - callbacks   : BatchCallbacks

Phát sự kiện qua callbacks (thread-safe, controller chuyển sang Qt signal).
"""

import os, time, json
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, Empty
from threading import Lock
from dataclasses import dataclass, field
from typing import Callable, Optional

from worker import run_scene

# ═══════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════

MAX_RETRIES  = 3
RETRY_DELAY  = 10   # giây
SLOTS_PER_ACC = 1   # Grok xử lý 1 video/lần per account


# ═══════════════════════════════════════════════════════════════
#  CALLBACKS  (controller sẽ wiring vào Qt signals)
# ═══════════════════════════════════════════════════════════════

@dataclass
class BatchCallbacks:
    """Tất cả callbacks mà batch runner sẽ gọi khi có sự kiện."""
    on_row_update : Callable[[int, str], None]          # (row_index, status_text)
    on_log        : Callable[[str], None]               # (message)
    on_stats      : Callable[[int,int,int,int], None]   # (total, running, done, error)
    on_status_bar : Callable[[str, str], None]          # (icon, message)
    on_done       : Callable[[], None]                  # hoàn thành tất cả
    is_cancelled  : Callable[[], bool] = field(
        default_factory=lambda: (lambda: False)
    )


# ═══════════════════════════════════════════════════════════════
#  LOAD ACCOUNTS  (tách từ run_batch.py)
# ═══════════════════════════════════════════════════════════════

ACCOUNTS_FOLDER = r"D:\grok-video-tool\accounts"
PROFILES_BASE   = r"D:\chrome-profiles"
SOURCE_PROFILE  = r"D:\chrome-debug-profile"
BASE_PORT       = 9222


def load_accounts(log=print) -> list:
    """
    Load toàn bộ accounts từ ACCOUNTS_FOLDER.
    Mỗi account có SLOTS_PER_ACC slot với port riêng + profile riêng.
    """
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from auth.session_manager import SessionManager
    from auth.exceptions import SessionCorruptedError

    def make_slots(name, port_start):
        return [
            {
                "port":        port_start + s,
                "profile_dir": os.path.join(PROFILES_BASE, f"{name}_slot{s}"),
            }
            for s in range(SLOTS_PER_ACC)
        ]

    accounts    = []
    port_cursor = BASE_PORT

    # Fallback: 1 account mặc định
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
            log(f"[ACC] account_01 (default) | port {slots[0]['port']}")
        return accounts

    for name in sorted(os.listdir(ACCOUNTS_FOLDER)):
        acc_dir = os.path.join(ACCOUNTS_FOLDER, name)
        if not os.path.isdir(acc_dir):
            continue
        sess = os.path.join(acc_dir, "session_state.json")
        mgr  = SessionManager(session_file=sess)
        if not mgr.exists():
            log(f"[ACC] ❌ {name} — chưa có session"); continue
        try:
            cookies = mgr.load()
            if not cookies: continue
        except SessionCorruptedError as e:
            log(f"[ACC] ❌ {name} — session lỗi: {e}"); continue

        slots = make_slots(name, port_cursor)
        port_cursor += SLOTS_PER_ACC

        meta = mgr.metadata()
        accounts.append({
            "id":             name,
            "session_path":   sess,
            "source_profile": SOURCE_PROFILE,
            "slots":          slots,
        })
        log(f"[ACC] ✅ {name} | {meta['cookie_count']} cookies | port {slots[0]['port']}")

    return accounts


# ═══════════════════════════════════════════════════════════════
#  DIVIDE & CONQUER
# ═══════════════════════════════════════════════════════════════

def divide_scenes(scenes: list, accounts: list) -> dict:
    """Chia scenes đều cho accounts (D&C). Trả về {account_id: [scene,...]}"""
    n_acc      = len(accounts)
    assignment = {acc["id"]: [] for acc in accounts}

    def _divide(sc_list, ac_list):
        if not sc_list or not ac_list: return
        if len(ac_list) == 1:
            assignment[ac_list[0]["id"]].extend(sc_list); return
        mid_s = len(sc_list) // 2
        mid_a = len(ac_list) // 2
        _divide(sc_list[:mid_s], ac_list[:mid_a])
        _divide(sc_list[mid_s:], ac_list[mid_a:])

    if len(scenes) <= n_acc:
        for i, scene in enumerate(scenes):
            assignment[accounts[i]["id"]].append(scene)
    else:
        _divide(scenes, accounts)

    return assignment


# ═══════════════════════════════════════════════════════════════
#  RETRY WRAPPER
# ═══════════════════════════════════════════════════════════════

def _run_with_retry(scene: dict, acc: dict, slot: dict,
                    cb: BatchCallbacks) -> dict:
    """Chạy 1 scene với retry, gọi cb.on_log khi cần."""
    last_result = None
    no_retry_errors = ["Không tìm thấy ảnh", "prompt", "FileNotFoundError"]

    for attempt in range(1, MAX_RETRIES + 1):
        if cb.is_cancelled():
            return {"scene": scene["name"], "status": "cancelled",
                    "output": None, "error": "Cancelled"}

        if attempt > 1:
            err_short = str(last_result.get("error", "?"))[:60]
            cb.on_log(f"🔄 Retry {scene['name']} lần {attempt}/{MAX_RETRIES} "
                      f"(lỗi: {err_short}) → chờ {RETRY_DELAY}s")
            time.sleep(RETRY_DELAY)

        result = run_scene(
            scene_name     = scene["name"],
            image_path     = scene.get("image"),
            prompt         = scene.get("prompt", ""),
            output_folder  = scene["output_folder"],
            port           = slot["port"],
            user_data_dir  = slot["profile_dir"],
            session_path   = acc["session_path"],
            source_profile = acc["source_profile"],
        )

        if result["status"] == "success":
            if attempt > 1:
                cb.on_log(f"✅ {scene['name']} thành công ở lần retry {attempt}")
            return result

        last_result = result
        if any(e in str(result.get("error", "")) for e in no_retry_errors):
            cb.on_log(f"⛔ {scene['name']} lỗi không thể retry: {result['error']}")
            return result

    cb.on_log(f"❌ {scene['name']} thất bại sau {MAX_RETRIES} lần retry")
    return last_result


# ═══════════════════════════════════════════════════════════════
#  ACCOUNT WORKER
# ═══════════════════════════════════════════════════════════════

def _run_account(acc: dict, chunk: list, global_queue: Queue,
                 cb: BatchCallbacks,
                 counters: dict, counters_lock: Lock,
                 total_scenes: int):
    """
    Xử lý chunk của 1 account.
    Slot pool: SLOTS_PER_ACC slot song song, hễ xong 1 → kéo scene mới ngay.
    """
    acc_id    = acc["id"]
    slots     = acc["slots"]
    slot_pool = Queue()
    local_q   = Queue()

    for s in chunk:
        local_q.put(s)
    for sl in slots:
        slot_pool.put(sl)

    def next_scene():
        try:    return local_q.get_nowait()
        except Empty: pass
        try:    return global_queue.get_nowait()
        except Empty: return None

    def plog(msg):
        cb.on_log(f"[{acc_id}] {msg}")

    plog(f"Bắt đầu | {len(chunk)} scenes | {len(slots)} slots")
    active: dict = {}   # future → (scene, slot)

    with ThreadPoolExecutor(max_workers=len(slots)) as pool:

        # Nạp đầy slots
        for _ in range(len(slots)):
            sc = next_scene()
            if sc is None: break
            sl = slot_pool.get()

            # Báo "đang chạy" ngay khi nạp vào slot
            with counters_lock:
                counters["running"] += 1
                cb.on_row_update(sc["row"], "⏳ Đang chạy")
                cb.on_stats(total_scenes, counters["running"],
                            counters["done"], counters["error"])
            cb.on_status_bar("⏳", f"Đang xử lý: {sc['name']}")

            f = pool.submit(_run_with_retry, sc, acc, sl, cb)
            active[f] = (sc, sl)
            plog(f"🚀 [{sc['name']}] → port {sl['port']}")

        while active:
            if cb.is_cancelled():
                break

            done_f             = next(as_completed(active))
            sc, sl             = active.pop(done_f)
            slot_pool.put(sl)  # trả slot về pool

            try:
                result = done_f.result()
            except Exception as e:
                result = {"scene": sc["name"], "status": "error",
                          "output": None, "error": str(e)}

            with counters_lock:
                counters["running"] -= 1
                if result["status"] == "success":
                    counters["done"] += 1
                    status_text = "✅ Xong"
                    icon = "✅"
                elif result["status"] == "cancelled":
                    status_text = "⏹ Đã huỷ"
                    icon = "⏹"
                else:
                    counters["error"] += 1
                    err_short = str(result.get("error", "Lỗi"))[:50]
                    status_text = f"❌ {err_short}"
                    icon = "❌"

                cb.on_row_update(sc["row"], status_text)
                cb.on_stats(total_scenes, counters["running"],
                            counters["done"], counters["error"])

            done_total = counters["done"] + counters["error"]
            cb.on_log(
                f"{icon} [{sc['name']}] [{done_total}/{total_scenes}] "
                f"port {sl['port']} | "
                f"{'→ ' + str(result.get('output','')) if result.get('output') else str(result.get('error',''))}"
            )

            # Kéo scene mới vào slot vừa giải phóng
            next_sc = next_scene()
            if next_sc and not cb.is_cancelled():
                free_slot = slot_pool.get()
                with counters_lock:
                    counters["running"] += 1
                    cb.on_row_update(next_sc["row"], "⏳ Đang chạy")
                    cb.on_stats(total_scenes, counters["running"],
                                counters["done"], counters["error"])
                cb.on_status_bar("⏳", f"Đang xử lý: {next_sc['name']}")
                f2 = pool.submit(_run_with_retry, next_sc, acc, free_slot, cb)
                active[f2] = (next_sc, free_slot)
                plog(f"🔄 [{next_sc['name']}] → port {free_slot['port']}")

    plog(f"Hoàn thành chunk")


# ═══════════════════════════════════════════════════════════════
#  ORCHESTRATOR (entry point từ controller)
# ═══════════════════════════════════════════════════════════════

def run_batch(scenes: list, output_folder: str,
              cb: BatchCallbacks,
              accounts: list | None = None):
    """
    Điểm khởi chạy từ controller.

    scenes         : list[dict]  — từ GeneratorController.build_scenes()
                     mỗi dict có: row, name, prompt, image (None nếu text mode)
    output_folder  : str
    cb             : BatchCallbacks
    accounts       : list[dict] | None  — None → tự load từ ACCOUNTS_FOLDER
    """
    if not scenes:
        cb.on_log("⚠️ Không có scene nào")
        cb.on_done()
        return

    # Gắn output_folder vào từng scene (worker cần biết)
    for sc in scenes:
        sc["output_folder"] = output_folder

    # Load accounts nếu chưa có
    if accounts is None:
        cb.on_log("🔍 Đang load accounts...")
        accounts = load_accounts(log=cb.on_log)

    if not accounts:
        cb.on_log("❌ Không có account nào khả dụng!")
        cb.on_done()
        return

    n_s, n_a = len(scenes), len(accounts)
    cb.on_log(f"📋 {n_s} scenes | {n_a} accounts | "
              f"{n_a * SLOTS_PER_ACC} slots song song tối đa")
    cb.on_status_bar("⏳", f"Chuẩn bị {n_s} scenes trên {n_a} accounts...")

    # Phân phối D&C
    assignment   = divide_scenes(scenes, accounts)
    global_queue = Queue()   # overflow queue (dùng khi D&C lệch)
    counters     = {"running": 0, "done": 0, "error": 0}
    counters_lock = Lock()

    # In kế hoạch
    for acc in accounts:
        chunk = assignment[acc["id"]]
        if chunk:
            names = ", ".join(s["name"] for s in chunk[:4])
            extra = f"..." if len(chunk) > 4 else ""
            cb.on_log(f"[PLAN] {acc['id']}: {len(chunk)} scenes → {names}{extra}")

    start_time = time.time()

    # Chạy mỗi account trong 1 thread
    with ThreadPoolExecutor(max_workers=n_a) as acc_pool:
        acc_futures = []
        for acc in accounts:
            chunk = assignment[acc["id"]]
            if not chunk:
                continue
            f = acc_pool.submit(
                _run_account,
                acc, chunk, global_queue, cb,
                counters, counters_lock, n_s,
            )
            acc_futures.append(f)

        for f in as_completed(acc_futures):
            try:
                f.result()
            except Exception as e:
                if "TargetClosedError" not in str(e):
                    cb.on_log(f"⚠️ Account lỗi: {e}")

    elapsed = time.time() - start_time
    done    = counters["done"]
    error   = counters["error"]

    summary = (f"🏁 Hoàn thành | ✅ {done} xong | ❌ {error} lỗi | "
               f"⏱ {elapsed:.0f}s")
    cb.on_log(summary)
    cb.on_status_bar("✅" if error == 0 else "⚠️", summary)

    # Lưu report
    try:
        os.makedirs(output_folder, exist_ok=True)
        report_path = os.path.join(output_folder, "batch_report.json")
        with open(report_path, "w", encoding="utf-8") as fp:
            json.dump({
                "total":   n_s,
                "success": done,
                "failed":  error,
                "elapsed": f"{elapsed:.0f}s",
            }, fp, ensure_ascii=False, indent=2)
        cb.on_log(f"📄 Report: {report_path}")
    except Exception as e:
        cb.on_log(f"WARN report: {e}")

    cb.on_done()