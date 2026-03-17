"""
controllers/generator_controller.py
Toàn bộ logic UI nằm ở đây.
Việc chạy video thật sự do batch_runner.py đảm nhiệm.
"""

from pathlib import Path
from threading import Thread, Event
from datetime import datetime
import os

from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtWidgets import QFileDialog, QTableWidgetItem

from batch_runner import BatchCallbacks, run_batch, load_accounts
from ui.log_dialog import LogDialog
from ui.scene_detail_dialog import SceneDetailDialog


# ═══════════════════════════════════════════════════════════════
#  Thread-safe bridge: worker threads → Qt main thread
# ═══════════════════════════════════════════════════════════════

class _Bridge(QObject):
    row_update    = Signal(int, str)            # (row, status_text)
    status_update = Signal(str, str)            # (icon, message)
    stats_update  = Signal(int, int, int, int)  # (total, running, done, error)
    log_line      = Signal(str)                 # 1 dòng log
    batch_done    = Signal()                    # hoàn thành toàn bộ


# ═══════════════════════════════════════════════════════════════
#  CONTROLLER
# ═══════════════════════════════════════════════════════════════

class GeneratorController:

    MODE_TEXT  = "text"
    MODE_IMAGE = "image"

    def __init__(self, ui):
        self.ui   = ui
        self.mode = self.MODE_TEXT

        # Trạng thái chạy
        self._is_running    = False
        self._cancel_event  = Event()
        self._total         = 0

        # Lưu đường dẫn video đã hoàn thành: {row: path}
        self._video_paths: dict[int, str] = {}

        # Cache accounts (load 1 lần, dùng nhiều lần)
        self._accounts: list | None = None

        # Bridge Qt thread-safe
        self._bridge = _Bridge()
        self._bridge.row_update.connect(self._on_row_update,    Qt.QueuedConnection)
        self._bridge.status_update.connect(self._on_status_update, Qt.QueuedConnection)
        self._bridge.stats_update.connect(self._on_stats_update,  Qt.QueuedConnection)
        self._bridge.log_line.connect(self._on_log_line,          Qt.QueuedConnection)
        self._bridge.batch_done.connect(self._on_batch_done,      Qt.QueuedConnection)

        # Log dialog (lazy)
        self._log_dialog: LogDialog | None = None

        self._connect_all()

    # ═══════════════════════════════════════════════════════════
    #  KẾT NỐI BUTTONS
    # ═══════════════════════════════════════════════════════════

    def _connect_all(self):
        ui = self.ui

        ui.btn_text.clicked.connect(self.set_text_mode)
        ui.btn_image.clicked.connect(self.set_image_mode)

        ui.btn_import_txt.clicked.connect(self.import_txt)
        ui.btn_clear.clicked.connect(self.clear_all)
        ui.btn_import_folder.clicked.connect(self.import_folder)
        ui.btn_browse.clicked.connect(self.choose_output)


        ui.btn_view_log.clicked.connect(self.open_log_dialog)
        ui.log_panel.open_fullscreen.connect(self.open_log_dialog)

        # Action bar: nút tạo lại + xem video (theo row đang chọn)
        ui.btn_regen_one.clicked.connect(self._on_regen_selected)
        ui.btn_open_video.clicked.connect(self._on_open_video_selected)

        # Khi thay đổi selection → cập nhật action bar
        ui.table.itemSelectionChanged.connect(self._on_selection_changed)

        # Double-click → mở dialog sửa prompt
        ui.table.cellDoubleClicked.connect(self._on_row_double_clicked)

    # ═══════════════════════════════════════════════════════════
    #  MODE
    # ═══════════════════════════════════════════════════════════

    def set_text_mode(self):
        if self.mode == self.MODE_TEXT: return
        self.mode = self.MODE_TEXT
        self._apply_mode()

    def set_image_mode(self):
        if self.mode == self.MODE_IMAGE: return
        self.mode = self.MODE_IMAGE
        self._apply_mode()

    def _apply_mode(self):
        is_text = self.mode == self.MODE_TEXT
        self.ui.prompt_card.setVisible(is_text)
        self.ui.image_card.setVisible(not is_text)
        self.ui.btn_text.setObjectName("TabToggle"    if is_text else "TabToggleOff")
        self.ui.btn_image.setObjectName("TabToggleOff" if is_text else "TabToggle")
        for btn in (self.ui.btn_text, self.ui.btn_image):
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.ui.table.setRowCount(0)
        self._reset_stats()

    # ═══════════════════════════════════════════════════════════
    #  IMPORT
    # ═══════════════════════════════════════════════════════════

    def import_txt(self):
        path, _ = QFileDialog.getOpenFileName(
            None, "Chọn file TXT", "", "Text files (*.txt)"
        )
        if not path: return
        lines = Path(path).read_text(encoding="utf-8").splitlines()
        lines = [l.strip() for l in lines if l.strip()]
        self.ui.prompt.setPlainText("\n".join(lines))
        self._load_table(lines)
        self._log(f"📄 Đã nhập {len(lines)} prompt từ: {path}")

    def import_folder(self):
        folder = QFileDialog.getExistingDirectory(None, "Chọn thư mục scenes")
        if not folder: return

        self._last_folder = folder
        path = Path(folder)
        subfolders = sorted([d for d in path.iterdir() if d.is_dir()])

        if subfolders:
            self._load_scene_table(subfolders)
            names = [d.name for d in subfolders]
            self.ui.lbl_image_count.setText(f"✅ {len(subfolders)} scene(s)")
            self._log(f"📁 {folder} → {len(subfolders)} scenes")
        else:
            exts = ("*.png", "*.jpg", "*.jpeg", "*.webp")
            images = []
            for ext in exts:
                images += sorted(path.glob(ext))
            names = [img.name for img in images]
            self.ui.lbl_image_count.setText(f"✅ {len(images)} ảnh")
            self._log(f"📁 {folder} → {len(images)} ảnh")

        # Sync vào prompt (ẩn) để build_scenes() đọc được
        self.ui.prompt.setPlainText("\n".join(names))
        self._load_table(names)

    def _load_scene_table(self, subfolders):
        tbl = self.ui.scene_table
        tbl.setRowCount(0)
        tbl.show()
        for i, folder in enumerate(subfolders):
            exts = (".png", ".jpg", ".jpeg", ".webp")
            img_count = sum(
                1 for f in folder.iterdir()
                if f.is_file() and f.suffix.lower() in exts
            )
            row = tbl.rowCount()
            tbl.insertRow(row)
            tbl.setItem(row, 0, QTableWidgetItem(str(i + 1)))
            tbl.setItem(row, 1, QTableWidgetItem(folder.name))
            tbl.setItem(row, 2, QTableWidgetItem(str(img_count)))

    # ═══════════════════════════════════════════════════════════
    #  MISC ACTIONS
    # ═══════════════════════════════════════════════════════════

    def clear_all(self):
        self.ui.prompt.clear()
        self.ui.table.setRowCount(0)
        self._reset_stats()
        self._log("🗑 Đã xóa toàn bộ")

    def choose_output(self):
        folder = QFileDialog.getExistingDirectory(None, "Chọn thư mục xuất")
        if folder:
            self.ui.out_path.setText(folder)
            self._log(f"📂 Thư mục xuất: {folder}")

    def retry_errors(self):
        if self._is_running: return
        pairs = self._collect_rows_by_status("❌")
        if not pairs:
            self._log("ℹ️ Không có scene lỗi để chạy lại"); return
        scenes = self.build_scenes()
        subset = [scenes[r] for r, _ in pairs if r < len(scenes)]
        self._log(f"🔄 Chạy lại {len(subset)} scene lỗi...")
        self._start_batch(subset)

    def retry_all(self):
        if self._is_running: return
        scenes = self.build_scenes()
        if not scenes: return
        self._reset_table_status()
        self._log(f"🔁 Tạo lại toàn bộ {len(scenes)} scenes...")
        self._start_batch(scenes)

    def retry_selected(self):
        if self._is_running: return
        items = self.ui.table.selectedItems()
        if not items: return
        selected_rows = sorted({item.row() for item in items})
        scenes = self.build_scenes()
        subset = [scenes[r] for r in selected_rows if r < len(scenes)]
        if subset:
            self._log(f"▶️ Tạo lại {len(subset)} scene được chọn...")
            self._start_batch(subset)

    # ═══════════════════════════════════════════════════════════
    #  START / STOP
    # ═══════════════════════════════════════════════════════════

    def toggle_generation(self):
        if self._is_running:
            self._stop_generation()
        else:
            self.start_generation()

    def start_generation(self):
        scenes = self.build_scenes()
        if not scenes:
            self._log("⚠️ Không có scene nào để chạy"); return
        output = self.ui.out_path.text().strip()
        if not output:
            self._log("⚠️ Chưa chọn thư mục xuất"); return

        self._reset_stats(total=len(scenes))
        self._log(f"🚀 Bắt đầu | {len(scenes)} scenes → {output}")
        self._start_batch(scenes, output)

    def _stop_generation(self):
        self._cancel_event.set()
        self._log("⏹ Đang dừng... (chờ scene hiện tại hoàn thành)")
        self.ui.btn_start.setText("⏳ Đang dừng...")
        self.ui.btn_start.setEnabled(False)

    def _start_batch(self, scenes: list, output_folder: str | None = None):
        if output_folder is None:
            output_folder = self.ui.out_path.text().strip()

        self._is_running   = True
        self._cancel_event.clear()
        self._total        = len(scenes)
        self._set_ui_running(True)

        cb = BatchCallbacks(
            on_row_update  = lambda row, st: self._bridge.row_update.emit(row, st),
            on_log         = lambda msg:     self._bridge.log_line.emit(self._fmt_log(msg)),
            on_stats       = lambda t,r,d,e: self._bridge.stats_update.emit(t,r,d,e),
            on_status_bar  = lambda ic, msg: self._bridge.status_update.emit(ic, msg),
            on_done        = lambda:         self._bridge.batch_done.emit(),
            is_cancelled   = self._cancel_event.is_set,
        )

        t = Thread(
            target=run_batch,
            args=(scenes, output_folder, cb),
            kwargs={"accounts": self._get_accounts()},
            daemon=True,
        )
        t.start()

    # ═══════════════════════════════════════════════════════════
    #  ACCOUNTS
    # ═══════════════════════════════════════════════════════════

    def _get_accounts(self) -> list | None:
        """
        Trả về danh sách accounts đã load.
        None → batch_runner tự load.
        Có thể gọi reload_accounts() để load lại.
        """
        return self._accounts   # None = để batch_runner tự load

    def reload_accounts(self):
        """Gọi thủ công nếu muốn load lại accounts từ đĩa."""
        self._log("🔍 Đang load accounts...")
        self._accounts = load_accounts(log=self._log)
        self._log(f"✅ Loaded {len(self._accounts)} accounts")

    # ═══════════════════════════════════════════════════════════
    #  BUILD SCENES
    # ═══════════════════════════════════════════════════════════

    def build_scenes(self) -> list:
        """
        TEXT mode  -> đọc từ self.ui.prompt (mỗi dòng = 1 prompt)
        IMAGE mode -> đọc trực tiếp từ self.ui.table (luôn đúng dù prompt bị ẩn)
        """
        scenes = []

        if self.mode == self.MODE_TEXT:
            lines = [
                l.strip()
                for l in self.ui.prompt.toPlainText().splitlines()
                if l.strip()
            ]
            for i, prompt in enumerate(lines, 1):
                scenes.append({
                    "row":    i - 1,
                    "name":   f"scene_{i:03d}",
                    "prompt": prompt,
                    "image":  None,
                })
        else:
            tbl    = self.ui.table
            folder = Path(getattr(self, "_last_folder", ""))

            for row in range(tbl.rowCount()):
                name_item = tbl.item(row, 1)
                if not name_item:
                    continue
                name = name_item.text().strip()
                if not name:
                    continue

                scene_dir   = folder / name if folder.exists() else None
                image_path  = None
                prompt_text = ""

                if scene_dir and scene_dir.is_dir():
                    for ext in ("jpg", "jpeg", "png", "webp"):
                        for fn in (f"image.{ext}", f"{name}.{ext}"):
                            p = scene_dir / fn
                            if p.exists():
                                image_path = str(p)
                                break
                        if image_path:
                            break
                    if not image_path:
                        for f in scene_dir.iterdir():
                            if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                                image_path = str(f)
                                break
                    prompt_file = scene_dir / "prompt.txt"
                    if prompt_file.exists():
                        prompt_text = prompt_file.read_text(encoding="utf-8").strip()
                else:
                    p = folder / name
                    if p.exists():
                        image_path = str(p)

                scenes.append({
                    "row":    row,
                    "name":   name,
                    "prompt": prompt_text,
                    "image":  image_path,
                })

        return scenes

    # ═══════════════════════════════════════════════════════════
    #  TABLE HELPERS
    # ═══════════════════════════════════════════════════════════

    def _load_table(self, items):
        tbl = self.ui.table
        tbl.setRowCount(0)
        self._video_paths.clear()
        for i, text in enumerate(items):
            row = tbl.rowCount()
            tbl.insertRow(row)
            tbl.setItem(row, 0, QTableWidgetItem(str(i + 1)))
            tbl.setItem(row, 1, QTableWidgetItem(text))
            tbl.setItem(row, 2, QTableWidgetItem("Chờ"))
        self._total = len(items)
        self._reset_stats(total=len(items))
        self._update_action_bar()

    def _reset_table_status(self):
        tbl = self.ui.table
        for r in range(tbl.rowCount()):
            tbl.setItem(r, 2, QTableWidgetItem("Chờ"))

    def _collect_rows_by_status(self, prefix: str):
        tbl = self.ui.table
        result = []
        for r in range(tbl.rowCount()):
            item = tbl.item(r, 2)
            if item and item.text().startswith(prefix):
                result.append((r, item.text()))
        return result

    # ── Action bar (dưới bảng) ────────────────────────────────

    def _selected_row(self) -> int | None:
        """Trả về row index đang được chọn, None nếu không có."""
        rows = self.ui.table.selectedItems()
        if not rows:
            return None
        return rows[0].row()

    def _update_action_bar(self):
        """Cập nhật action bar theo row đang chọn."""
        row = self._selected_row()
        ui  = self.ui

        if row is None:
            ui.lbl_selected.setText("Chọn 1 dòng để thao tác")
            ui.btn_regen_one.setEnabled(False)
            ui.btn_open_video.setEnabled(False)
            return

        name_item   = ui.table.item(row, 1)
        status_item = ui.table.item(row, 2)
        name   = name_item.text()   if name_item   else f"row {row+1}"
        status = status_item.text() if status_item else ""

        ui.lbl_selected.setText(f"#{row+1}  {name[:40]}")
        ui.btn_regen_one.setEnabled(not self._is_running)

        # Nút xem video: chỉ enable khi đã xong VÀ có file
        has_video = (row in self._video_paths and
                     os.path.exists(self._video_paths[row]))
        ui.btn_open_video.setEnabled(has_video)

    def _on_selection_changed(self):
        self._update_action_bar()

    def _on_regen_selected(self):
        """Tạo lại row đang chọn (nút ▶ Tạo lại trên action bar)."""
        row = self._selected_row()
        if row is None: return
        if self._is_running:
            self._log("⚠️ Đang chạy, không thể tạo lại lúc này"); return
        scenes = self.build_scenes()
        if row >= len(scenes): return
        scene = scenes[row]
        self.ui.table.setItem(row, 2, QTableWidgetItem("Chờ"))
        self._log(f"🔄 Tạo lại [{scene['name']}]...")
        self._start_batch([scene])

    def _on_open_video_selected(self):
        """Mở video của row đang chọn."""
        row = self._selected_row()
        if row is None:
            self._log("⚠️ Chưa chọn dòng nào"); return

        path = self._video_paths.get(row)

        # Nếu chưa có trong cache → thử scan lại
        if not path:
            output = self.ui.out_path.text().strip()
            scenes = self.build_scenes()
            if row < len(scenes):
                scene_name = scenes[row].get("name", f"scene_{row+1:03d}")
                for ext in ("mp4", "webm"):
                    p = os.path.join(output, f"{scene_name}.{ext}")
                    if os.path.exists(p):
                        self._video_paths[row] = p
                        path = p
                        break

        if not path:
            self._log(f"⚠️ Không tìm thấy video. "
                      f"Kiểm tra thư mục: {self.ui.out_path.text().strip()}")
            return

        if not os.path.exists(path):
            self._log(f"⚠️ File không tồn tại: {path}"); return

        self._log(f"🎥 Mở: {path}")
        try:
            os.startfile(path)
        except AttributeError:
            import subprocess
            subprocess.Popen(["xdg-open", path])

    # ═══════════════════════════════════════════════════════════
    #  LOG
    # ═══════════════════════════════════════════════════════════

    def _fmt_log(self, message: str) -> str:
        ts = datetime.now().strftime("%H:%M:%S")
        return f"[{ts}] {message}"

    def _log(self, message: str):
        """Log từ main thread — ghi thẳng vào panel."""
        line = self._fmt_log(message)
        self.ui.log_panel.append(line)
        if self._log_dialog is not None:
            self._log_dialog.append(line)

    def open_log_dialog(self):
        if self._log_dialog is None:
            self._log_dialog = LogDialog(self.ui)
            existing = self.ui.log_panel.get_text()
            if existing:
                for ln in existing.splitlines():
                    self._log_dialog.append(ln)
        self._log_dialog.show()
        self._log_dialog.raise_()
        self._log_dialog.activateWindow()

    # ═══════════════════════════════════════════════════════════
    #  UI STATE HELPERS
    # ═══════════════════════════════════════════════════════════

    def _set_ui_running(self, running: bool):
        """Đổi trạng thái nút Start ↔ Stop."""
        if running:
            self.ui.btn_start.setText("⏹  Dừng lại")
            self.ui.btn_start.setObjectName("BtnStop")
        else:
            self.ui.btn_start.setText("▶  Bắt đầu tạo video")
            self.ui.btn_start.setObjectName("BtnStart")
        self.ui.btn_start.setEnabled(True)
        self.ui.btn_start.style().unpolish(self.ui.btn_start)
        self.ui.btn_start.style().polish(self.ui.btn_start)

    # ═══════════════════════════════════════════════════════════
    #  THREAD-SAFE SLOTS (chỉ gọi từ main thread qua QueuedConnection)
    # ═══════════════════════════════════════════════════════════

    def _on_row_update(self, row: int, status: str):
        self.ui.table.setItem(row, 2, QTableWidgetItem(status))

        # Khi xong → lưu video path
        if "✅" in status:
            output = self.ui.out_path.text().strip()
            if output:
                # Tên file video = scene name (scene_001, scene_002...)
                # không phải prompt text hiển thị trong bảng
                scene_name = f"scene_{row+1:03d}"
                for ext in ("mp4", "webm"):
                    p = os.path.join(output, f"{scene_name}.{ext}")
                    if os.path.exists(p):
                        self._video_paths[row] = p
                        self._log(f"🎥 Video sẵn sàng: {p}")
                        break
                else:
                    # Fallback: scan toàn bộ output folder tìm file mới nhất
                    self._scan_video_for_row(row, output)

        # Refresh action bar nếu row này đang được chọn
        if self._selected_row() == row:
            self._update_action_bar()

    def _scan_video_for_row(self, row: int, output: str):
        """Fallback: tìm file video trong output folder theo nhiều pattern."""
        tbl       = self.ui.table
        name_item = tbl.item(row, 1)
        if not name_item:
            return

        # Thử các pattern tên file khác nhau
        name_in_table = name_item.text().strip()
        candidates = [
            f"scene_{row+1:03d}",           # scene_001
            f"scene_{row+1}",               # scene_1
            name_in_table[:30],             # prompt text (image mode)
        ]

        for stem in candidates:
            for ext in ("mp4", "webm"):
                p = os.path.join(output, f"{stem}.{ext}")
                if os.path.exists(p):
                    self._video_paths[row] = p
                    return

    def _on_row_double_clicked(self, row: int, _col: int):
        """Double-click → mở dialog chỉnh sửa prompt."""
        tbl = self.ui.table
        name_item   = tbl.item(row, 1)
        status_item = tbl.item(row, 2)
        if not name_item: return

        scene_name = name_item.text()
        status     = status_item.text() if status_item else "Chờ"

        scenes = self.build_scenes()
        prompt = scenes[row]["prompt"] if row < len(scenes) else ""


        dlg = SceneDetailDialog(
            row        = row,
            scene_name = scene_name,
            prompt     = prompt,
            status     = status,
            parent     = self.ui,
        )
        dlg.prompt_saved.connect(self._on_prompt_saved)
        dlg.exec()

    def _on_prompt_saved(self, row: int, new_prompt: str):
        """Lưu prompt mới vào UI (text mode: cập nhật QTextEdit)."""
        if self.mode == self.MODE_TEXT:
            lines = self.ui.prompt.toPlainText().splitlines()
            if row < len(lines):
                lines[row] = new_prompt
                self.ui.prompt.setPlainText("\n".join(lines))
        self._log(f"💾 Đã lưu prompt mới cho row {row + 1}")

    def _on_status_update(self, icon: str, message: str):
        self.ui.lbl_status_icon.setText(icon)
        self.ui.lbl_status.setText(message)

    def _on_stats_update(self, total: int, running: int, done: int, error: int):
        self.ui.s_total.set_value(total)
        self.ui.s_running.set_value(running)
        self.ui.s_done.set_value(done)
        self.ui.s_error.set_value(error)

    def _on_log_line(self, line: str):
        """Nhận log từ worker thread (đã format timestamp)."""
        self.ui.log_panel.append(line)
        if self._log_dialog is not None:
            self._log_dialog.append(line)

    def _on_batch_done(self):
        self._is_running = False
        self._cancel_event.clear()
        self._set_ui_running(False)

        # Scan output folder để map video files → row index
        output = self.ui.out_path.text().strip()
        if output and os.path.exists(output):
            # Lấy tất cả scenes để biết tên đúng của từng row
            scenes = self.build_scenes()
            for row, scene in enumerate(scenes):
                scene_name = scene.get("name", f"scene_{row+1:03d}")
                for ext in ("mp4", "webm"):
                    p = os.path.join(output, f"{scene_name}.{ext}")
                    if os.path.exists(p):
                        self._video_paths[row] = p
                        break

        self._update_action_bar()

    # ═══════════════════════════════════════════════════════════
    #  STATS HELPERS
    # ═══════════════════════════════════════════════════════════

    def _reset_stats(self, total: int = 0):
        self.ui.s_total.set_value(total)
        self.ui.s_running.set_value(0)
        self.ui.s_done.set_value(0)
        self.ui.s_error.set_value(0)