"""
ui/login_panel.py — Tab Tài khoản
2 bước: [🔑 Login] → mở Chrome  |  [💾 Lưu Session] → lấy cookie
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QTableWidget, QTableWidgetItem, QPushButton, QTextEdit,
    QHeaderView, QAbstractItemView, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt, QDateTime
from PySide6.QtGui import QFont, QColor

from accounts.account_controller import AccountController
from ui.account_dialog import AccountDialog

# ── THÊM MỚI ──────────────────────────────────────────────────
from auth.auto_login import (
    AutoLoginWorker, AutoLoginAllWorker, LoginConfig, load_coords
)
from ui.coord_picker_dialog import CoordPickerDialog
from pathlib import Path
# ──────────────────────────────────────────────────────────────

_STATUS_BG = {
    "logged_in":  "#238636",
    "pending":    "#9e6a03",
    "error":      "#da3633",
    "opening":    "#1f6feb",
    "saving":     "#6e40c9",
}

def _btn(text, obj, h=32, w=None):
    b = QPushButton(text)
    b.setObjectName(obj)
    b.setFixedHeight(h)
    if w: b.setFixedWidth(w)
    return b


class LoginPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.ctrl = AccountController()
        self.ctrl.on_data_changed(self._refresh)
        # Trạng thái nội bộ: slot → "opening" | "saving" | None
        self._states: dict = {}
        self._build()
        self._refresh()
        # ── THÊM MỚI ──────────────────────────────────────────
        self._auto_workers: dict = {}  # slot → AutoLoginWorker
        # ──────────────────────────────────────────────────────

    # ─────────────────────────── BUILD ───────────────────────────
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # Stats bar
        stats = QFrame(); stats.setObjectName("PanelCard"); stats.setFixedHeight(50)
        sl = QHBoxLayout(stats); sl.setContentsMargins(18, 0, 18, 0)
        icon_t = QLabel("📋"); icon_t.setFont(QFont("Segoe UI Emoji", 14))
        self.lbl_total  = QLabel("Total: 0")
        self.lbl_total.setFont(QFont("Segoe UI", 13, QFont.Bold))
        icon_l = QLabel("✅"); icon_l.setFont(QFont("Segoe UI Emoji", 14))
        self.lbl_logged = QLabel("Logged in: 0")
        self.lbl_logged.setFont(QFont("Segoe UI", 13, QFont.Bold))
        sl.addWidget(icon_t); sl.addSpacing(6); sl.addWidget(self.lbl_total)
        sl.addStretch()
        sl.addWidget(icon_l); sl.addSpacing(6); sl.addWidget(self.lbl_logged)
        root.addWidget(stats)

        # Account card
        card = QFrame(); card.setObjectName("PanelCard")
        cl = QVBoxLayout(card); cl.setContentsMargins(14, 12, 14, 14); cl.setSpacing(10)

        tr = QHBoxLayout()
        ti = QLabel("📋"); ti.setFont(QFont("Segoe UI Emoji", 13))
        tt = QLabel("Account List"); tt.setObjectName("SectionTitle")
        tr.addWidget(ti); tr.addSpacing(6); tr.addWidget(tt); tr.addStretch()
        cl.addLayout(tr)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["#", "Email", "Status", "Last Login", "Cookies", "Chrome"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Fixed)
        hh.setSectionResizeMode(3, QHeaderView.Fixed)
        hh.setSectionResizeMode(4, QHeaderView.Fixed)
        hh.setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 44)
        self.table.setColumnWidth(2, 110)
        self.table.setColumnWidth(3, 140)
        self.table.setColumnWidth(4, 74)
        self.table.setColumnWidth(5, 90)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setMinimumHeight(220)
        self.table.setFrameShape(QFrame.NoFrame)
        self.table.doubleClicked.connect(self._on_edit)
        cl.addWidget(self.table)

        # ── Buttons ───────────────────────────────────────────────
        br = QHBoxLayout(); br.setSpacing(6)

        # CRUD
        for txt, obj, fn in [
            ("➕ Add",         "BtnGreen",  self._on_add),
            ("✏️ Edit",         "BtnGray",   self._on_edit),
            ("🗑 Delete",       "BtnRed",    self._on_delete),
            ("🗑 Xóa tất cả",  "BtnRed",    self._on_clear),
            ("✔️ Chon tất cả", "BtnGray",   self.table.selectAll),
        ]:
            b = _btn(txt, obj, 34); b.clicked.connect(fn); br.addWidget(b)

        # Separator nhỏ
        sep = QFrame(); sep.setFrameShape(QFrame.VLine)
        sep.setFixedHeight(28); sep.setObjectName("VSep")
        br.addSpacing(4); br.addWidget(sep); br.addSpacing(4)

        # Login + Lưu Session (cặp đôi)
        self.btn_login = _btn("🔑 Login",         "BtnBlue",   34)
        self.btn_save  = _btn("💾 Lưu Session",   "BtnPurple", 34)
        self.btn_login.clicked.connect(self._on_login)
        self.btn_save.clicked.connect(self._on_save_session)
        br.addWidget(self.btn_login)
        br.addWidget(self.btn_save)

        # ── THÊM MỚI: separator + 3 nút auto login ───────────────
        sep2 = QFrame(); sep2.setFrameShape(QFrame.VLine)
        sep2.setFixedHeight(28); sep2.setObjectName("VSep")
        br.addSpacing(4); br.addWidget(sep2); br.addSpacing(4)

        self.btn_auto_one  = _btn("🤖 Auto Login", "BtnTeal", 34)
        self.btn_auto_all  = _btn("🤖 Login All",  "BtnTeal", 34)
        self.btn_calibrate = _btn("🎯 Tọa độ",     "BtnGray", 34)
        self.btn_auto_one.setToolTip("Tự động đăng nhập account đang chọn")
        self.btn_auto_all.setToolTip("Tự động đăng nhập tất cả accounts")
        self.btn_calibrate.setToolTip("Cấu hình tọa độ màn hình")
        self.btn_auto_one.clicked.connect(self._on_auto_one)
        self.btn_auto_all.clicked.connect(self._on_auto_all)
        self.btn_calibrate.clicked.connect(self._on_calibrate)
        br.addWidget(self.btn_auto_one)
        br.addWidget(self.btn_auto_all)
        br.addWidget(self.btn_calibrate)
        # ─────────────────────────────────────────────────────────

        br.addSpacing(4)
        # Import / Export
        for txt, obj, fn in [
            ("📄 Nhập TXT",  "BtnTeal",   self._on_import),
            ("📤 Export",    "BtnGray",   self._on_export),
        ]:
            b = _btn(txt, obj, 34); b.clicked.connect(fn); br.addWidget(b)

        br.addStretch()
        cl.addLayout(br)
        root.addWidget(card)

        # Log card
        log_card = QFrame(); log_card.setObjectName("PanelCard")
        ll = QVBoxLayout(log_card); ll.setContentsMargins(14, 10, 14, 12); ll.setSpacing(8)
        log_tr = QHBoxLayout(); log_tr.setContentsMargins(0, 0, 0, 0)
        log_ti = QLabel("📝"); log_ti.setFont(QFont("Segoe UI Emoji", 11))
        log_tt = QLabel("Log"); log_tt.setObjectName("SectionTitle")
        log_tr.addWidget(log_ti); log_tr.addSpacing(10); log_tr.addWidget(log_tt)
        log_tr.addStretch()
        btn_clr = _btn("✖ Clear", "BtnGray", 26, 72)
        btn_clr.clicked.connect(lambda: self.log_area.clear())
        log_tr.addWidget(btn_clr)
        ll.addLayout(log_tr)

        self.log_area = QTextEdit()
        self.log_area.setObjectName("LogArea")
        self.log_area.setReadOnly(True)
        self.log_area.setFixedHeight(190)
        self.log_area.setPlaceholderText("Log output sẽ hiển thị ở đây...")
        ll.addWidget(self.log_area)
        root.addWidget(log_card)

    # ─────────────────────────── REFRESH ─────────────────────────
    def _refresh(self):
        rows = self.ctrl.get_rows()
        self.lbl_total.setText(f"Total: {self.ctrl.total()}")
        self.lbl_logged.setText(f"Logged in: {self.ctrl.total_logged()}")
        self.table.setRowCount(len(rows))

        for r in rows:
            row   = r.index - 1
            state = self._states.get(r.slot)   # "opening" | "saving" | None

            # Chọn status hiển thị
            if state == "opening":
                status_txt = "🔄 Đang mở..."
                status_bg  = _STATUS_BG["opening"]
            elif state == "saving":
                status_txt = "⏳ Đang lưu..."
                status_bg  = _STATUS_BG["saving"]
            else:
                status_txt = r.status
                status_bg  = _STATUS_BG.get(r.status, "#555")

            def mk(text, align=Qt.AlignVCenter | Qt.AlignLeft, slot=r.slot):
                it = QTableWidgetItem(str(text))
                it.setTextAlignment(align)
                it.setData(Qt.UserRole, slot)
                return it

            self.table.setItem(row, 0, mk(r.index, Qt.AlignCenter))
            self.table.setItem(row, 1, mk(f"  {r.email}"))

            s = mk(status_txt, Qt.AlignCenter)
            s.setBackground(QColor(status_bg))
            s.setForeground(QColor("#ffffff"))
            self.table.setItem(row, 2, s)

            self.table.setItem(row, 3, mk(r.last_login, Qt.AlignCenter))
            self.table.setItem(row, 4, mk(r.cookies, Qt.AlignCenter))

            ch = mk("🔓 Mở", Qt.AlignCenter)
            ch.setBackground(QColor("#d29922")); ch.setForeground(QColor("#ffffff"))
            self.table.setItem(row, 5, ch)
            self.table.setRowHeight(row, 38)

    # ─────────────────────────── HELPERS ─────────────────────────
    def _log(self, msg: str):
        ts = QDateTime.currentDateTime().toString("hh:mm:ss")
        self.log_area.append(f"[{ts}]  {msg}")

    def _selected_slots(self) -> list:
        rows = sorted(set(i.row() for i in self.table.selectedIndexes()))
        slots = []
        for row in rows:
            item = self.table.item(row, 0)
            if item:
                s = item.data(Qt.UserRole)
                if s: slots.append(s)
        return slots

    def _first_slot(self):
        s = self._selected_slots()
        return s[0] if s else None

    def _set_state(self, slot: str, state):
        if state is None:
            self._states.pop(slot, None)
        else:
            self._states[slot] = state
        self._refresh()

    # ─────────────────────────── CRUD ────────────────────────────

    def _on_add(self):
        dlg = AccountDialog(self, mode="add")
        if dlg.exec() != AccountDialog.Accepted: return
        ok, msg = self.ctrl.add(dlg.out_email, dlg.out_password)
        self._log(("✅ " if ok else "❌ ") + msg)
        if not ok:
            QMessageBox.warning(self, "Không thể thêm", msg)

    def _on_edit(self):
        slot = self._first_slot()
        if not slot:
            QMessageBox.information(self, "Thông báo", "Chọn tài khoản cần sửa!")
            return
        dlg = AccountDialog(self, mode="edit",
                            email=self.ctrl.get_email_by_slot(slot),
                            password=self.ctrl.get_password_by_slot(slot),
                            slot=slot)
        if dlg.exec() != AccountDialog.Accepted: return
        ok, msg = self.ctrl.edit(slot, dlg.out_password)
        self._log(("✅ " if ok else "❌ ") + msg)

    def _on_delete(self):
        slots = self._selected_slots()
        if not slots:
            QMessageBox.information(self, "Thông báo", "Chọn tài khoản cần xóa!"); return
        lines = "\n".join(f"  •  {s}  —  {self.ctrl.get_email_by_slot(s)}" for s in slots)
        reply = QMessageBox.question(
            self, "Xác nhận xóa",
            f"Xóa {len(slots)} tài khoản?\n\n{lines}\n\n⚠️  Không thể hoàn tác.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            n, msg = self.ctrl.delete(slots)
            self._log(f"🗑 {msg}")

    def _on_clear(self):
        total = self.ctrl.total()
        if total == 0: self._log("ℹ️  Danh sách trống"); return
        r1 = QMessageBox.warning(
            self, "⚠️  Xóa tất cả",
            f"Xóa TẤT CẢ {total} tài khoản + session?\nKhông thể hoàn tác!",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if r1 != QMessageBox.Yes: return
        r2 = QMessageBox.critical(
            self, "Xác nhận lần cuối",
            f"Xóa vĩnh viễn {total} tài khoản?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if r2 == QMessageBox.Yes:
            self._log(f"🗑 {self.ctrl.delete_all()}")

    # ─────────────────────────── LOGIN ───────────────────────────

    def _on_login(self):
        """Bước 1: Mở Chrome — KHÔNG tự lưu session."""
        slots = self._selected_slots()
        if not slots:
            QMessageBox.information(self, "Thông báo",
                "Chọn tài khoản cần login!"); return

        for slot in slots:
            email = self.ctrl.get_email_by_slot(slot)
            port  = self.ctrl.get_port(slot)
            self._log(f"[{slot}] 🔑 Mở Chrome cho: {email} (port {port})")
            self._set_state(slot, "opening")

            self.ctrl.start_login(
                slot           = slot,
                on_log         = self._log,
                on_chrome_ready= self._on_chrome_ready,
                on_failed      = self._on_login_failed,
            )

    def _on_chrome_ready(self, slot: str, port: int):
        """Chrome đã mở — nhắc người dùng đăng nhập rồi nhấn Lưu Session."""
        self._set_state(slot, None)
        email = self.ctrl.get_email_by_slot(slot)
        self._log(f"[{slot}] ✅ Chrome đã mở — port {port}")
        self._log(f"[{slot}] ─────────────────────────────────────────")
        self._log(f"[{slot}] 👉 Đăng nhập tài khoản [{email}] trong Chrome")
        self._log(f"[{slot}] 👉 Sau khi vào được Grok → nhấn  💾 Lưu Session")
        self._log(f"[{slot}] ─────────────────────────────────────────")

    def _on_login_failed(self, slot: str, msg: str):
        self._set_state(slot, None)
        self._log(f"[{slot}] ❌ Mở Chrome thất bại: {msg}")
        QMessageBox.critical(self, f"Lỗi — {slot}", msg)

    # ─────────────────────── LƯU SESSION ─────────────────────────

    def _on_save_session(self):
        """Bước 2: Kết nối Chrome đang mở → lấy cookie → lưu."""
        slots = self._selected_slots()
        if not slots:
            QMessageBox.information(self, "Thông báo",
                "Chọn tài khoản cần lưu session!"); return

        for slot in slots:
            # Kiểm tra Chrome còn mở không
            if not self.ctrl.is_chrome_open(slot):
                port  = self.ctrl.get_port(slot)
                email = self.ctrl.get_email_by_slot(slot)
                reply = QMessageBox.warning(
                    self,
                    "Chrome đã đóng",
                    f"Cổng {port} của [{slot}] đã đóng.\n\n"
                    f"Chrome đã bị tắt!\n"
                    f"Bạn cần nhấn Login để mở lại và đăng nhập tài khoản:\n  {email}",
                    QMessageBox.Ok)
                self._log(f"[{slot}] ⚠️  Chrome đã đóng — cần Login lại")
                continue

            email = self.ctrl.get_email_by_slot(slot)
            port  = self.ctrl.get_port(slot)
            self._log(f"[{slot}] 💾 Đang lấy cookies từ Chrome port {port}...")
            self._set_state(slot, "saving")

            self.ctrl.save_session(
                slot   = slot,
                on_log = self._log,
                on_done= self._on_save_done,
            )

    def _on_save_done(self, slot: str, ok: bool, msg: str):
        self._set_state(slot, None)
        icon = "✅" if ok else "❌"
        self._log(f"{icon} [{slot}] {msg}")

        if not ok and "chưa đăng nhập" in msg.lower():
            QMessageBox.warning(
                self, "Chưa đăng nhập",
                f"[{slot}] Bạn chưa đăng nhập Grok trong Chrome!\n\n"
                "Hãy đăng nhập xong rồi nhấn 💾 Lưu Session lại.")

    # ─────────────────────── IMPORT / EXPORT ─────────────────────

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Nhập TXT", "", "Text files (*.txt);;All files (*)")
        if path: self._log(f"📄 {self.ctrl.import_txt(path)}")

    def _on_export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export TXT", "accounts.txt", "Text files (*.txt)")
        if path: self._log(f"📤 {self.ctrl.export_txt(path)}")

    # ── THÊM MỚI: AUTO LOGIN ─────────────────────────────────────

    def _on_calibrate(self):
        """Mở dialog cấu hình tọa độ màn hình."""
        dlg = CoordPickerDialog(self)
        dlg.exec()

    def _on_auto_one(self):
        """Auto login 1 account đang chọn."""
        slot = self._first_slot()
        if not slot:
            QMessageBox.information(self, "Thông báo",
                "Chọn 1 tài khoản để Auto Login!"); return
        self._run_auto_queue([slot])

    def _on_auto_all(self):
        """Auto login TẤT CẢ accounts CÙNG LÚC (song song)."""
        rows  = self.ctrl.get_rows()
        slots = [r.slot for r in rows]
        if not slots:
            QMessageBox.information(self, "Thông báo",
                "Không có tài khoản nào!"); return
        reply = QMessageBox.question(
            self, "Login All (Song song)",
            f"Tự động đăng nhập {len(slots)} tài khoản CÙNG LÚC?\n\n"
            f"Mỗi account mở 1 Chrome riêng → chạy song song.\n"
            f"⚠️  Nếu có Cloudflare, cần click vào từng cửa sổ.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes: return

        # Đánh dấu tất cả đang "opening"
        for slot in slots:
            self._set_state(slot, "opening")

        # Dùng AutoLoginAllWorker — chạy song song tất cả
        w = AutoLoginAllWorker(slots)
        w.log_msg.connect(self._log)
        w.slot_done.connect(self._on_auto_done_parallel)
        w.all_done.connect(lambda: self._log("🏁 Hoàn thành Login All"))
        self._auto_workers["__all__"] = w
        w.start()

    def _on_auto_done_parallel(self, slot: str, ok: bool, msg: str):
        """Callback khi 1 slot trong parallel batch xong."""
        self._set_state(slot, None)
        self._log(f"{'✅' if ok else '❌'} [{slot}] {msg}")
        if ok:
            self._log(f"[{slot}] 💾 Tự động lưu session...")
            self.ctrl.save_session(
                slot   = slot,
                on_log = self._log,
                on_done= lambda s, o, m:
                    self._log(f"{'✅' if o else '❌'} [{s}] Session: {m}"),
            )

    def _run_auto_queue(self, slots: list):
        """Lấy slot đầu queue, chạy AutoLoginWorker, khi xong gọi tiếp slot sau."""
        if not slots: return
        slot = slots[0]
        rest = slots[1:]

        if slot in self._auto_workers:
            self._log(f"[{slot}] ⚠️  Đang chạy, bỏ qua"); return

        # LoginConfig tự đọc email/password từ accounts/<slot>/info.json
        cfg = LoginConfig(
            slot   = slot,
            coords = load_coords(),
        )

        if not cfg.email or not cfg.password:
            self._log(f"[{slot}] ❌ Không tìm thấy email/password trong info.json")
            if rest:
                self._run_auto_queue(rest)
            return

        self._log(f"[{slot}] 🤖 Auto login: {cfg.email}")
        self._set_state(slot, "opening")

        w = AutoLoginWorker(cfg)
        w.log_msg.connect(self._log)
        w.finished.connect(
            lambda s, ok, msg, _rest=rest:
                self._on_auto_done(s, ok, msg, _rest)
        )
        self._auto_workers[slot] = w
        w.start()

    def _on_auto_done(self, slot: str, ok: bool, msg: str, remaining: list):
        """Callback khi 1 auto login xong → tự lưu session + chạy slot tiếp."""
        self._auto_workers.pop(slot, None)
        self._set_state(slot, None)
        self._log(f"{'✅' if ok else '❌'} [{slot}] {msg}")

        if ok:
            self._log(f"[{slot}] 💾 Tự động lưu session...")
            self.ctrl.save_session(
                slot   = slot,
                on_log = self._log,
                on_done= lambda s, o, m:
                    self._log(f"{'✅' if o else '❌'} [{s}] Session: {m}"),
            )

        if remaining:
            self._log(f"⏭  Chuyển sang: {remaining[0]} (sau 3s...)")
            # Dùng QTimer thay time.sleep để không block UI
            from PySide6.QtCore import QTimer
            QTimer.singleShot(3000, lambda: self._run_auto_queue(remaining))
        else:
            self._log("🏁 Hoàn thành Login All")

    # ─────────────────────────────────────────────────────────────