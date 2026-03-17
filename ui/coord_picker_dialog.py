"""
ui/coord_picker_dialog.py
─────────────────────────
Dialog chọn tọa độ màn hình cho auto login.
Hiển thị tọa độ chuột realtime, nhấn 📍 để chốt từng điểm.
"""

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QSizePolicy, QWidget
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor

try:
    import pyautogui as pg
    HAS_PG = True
except ImportError:
    HAS_PG = False

from auth.auto_login import COORDS_FILE, DEFAULT_COORDS, save_coords

# ────────────────────────────────────────────────────────────────

FIELDS = [
    ("cloudflare_check", "Checkbox Cloudflare",
     "Khi CF xuất hiện: di chuột vào ô vuông checkbox 'I am human' → 📍 Chốt"),
]


def _btn(text, obj, h=32, w=None):
    b = QPushButton(text)
    b.setObjectName(obj)
    b.setFixedHeight(h)
    if w: b.setFixedWidth(w)
    return b


class CoordPickerDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🎯 Cấu hình tọa độ Auto Login")
        self.setMinimumSize(660, 500)
        self.setWindowFlags(
            Qt.Dialog |
            Qt.WindowCloseButtonHint |
            Qt.WindowMaximizeButtonHint |
            Qt.WindowStaysOnTopHint
        )
        self._coords = self._load()
        self._build()

        # Timer realtime cursor
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(80)

    # ─────────────────────────────────────────────────────────────
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        # Title
        t = QLabel("🎯  Cấu hình tọa độ màn hình")
        t.setFont(QFont("Segoe UI", 13, QFont.Bold))
        root.addWidget(t)

        hint = QLabel(
            "Mở Chrome đến trang đăng nhập Grok, "
            "di chuột đến từng vị trí rồi nhấn  📍 Chốt  để lưu tọa độ."
        )
        hint.setObjectName("HintLabel")
        hint.setWordWrap(True)
        root.addWidget(hint)

        # Cursor realtime
        cframe = QFrame(); cframe.setObjectName("Card")
        cl = QHBoxLayout(cframe)
        cl.setContentsMargins(12, 8, 12, 8)
        cl.addWidget(QLabel("📍 Tọa độ chuột:"))
        self.lbl_pos = QLabel("(—, —)")
        self.lbl_pos.setFont(QFont("Consolas", 13, QFont.Bold))
        self.lbl_pos.setObjectName("StatNumTotal")
        cl.addWidget(self.lbl_pos)
        cl.addStretch()

        if not HAS_PG:
            warn = QLabel("⚠️ pyautogui chưa cài — pip install pyautogui")
            warn.setObjectName("StatNumError")
            cl.addWidget(warn)

        root.addWidget(cframe)

        # Table
        self.tbl = QTableWidget(len(FIELDS), 4)
        self.tbl.setHorizontalHeaderLabels(["Key", "Trường", "Tọa độ", ""])
        hh = self.tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Fixed)
        hh.setSectionResizeMode(3, QHeaderView.Fixed)
        self.tbl.setColumnWidth(0, 150)
        self.tbl.setColumnWidth(2, 105)
        self.tbl.setColumnWidth(3, 82)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.verticalHeader().setDefaultSectionSize(36)
        self.tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl.setFrameShape(QFrame.NoFrame)
        self.tbl.setSelectionBehavior(QTableWidget.SelectRows)

        for i, (key, label, _hint) in enumerate(FIELDS):
            it0 = QTableWidgetItem(key)
            it0.setFont(QFont("Consolas", 9))
            self.tbl.setItem(i, 0, it0)
            self.tbl.setItem(i, 1, QTableWidgetItem(label))

            coords = self._coords.get(key)
            txt = f"({coords[0]}, {coords[1]})" if coords else "—"
            it2 = QTableWidgetItem(txt)
            it2.setTextAlignment(Qt.AlignCenter)
            self.tbl.setItem(i, 2, it2)

            # Nút Chốt trong cell
            w = QWidget()
            lay = QHBoxLayout(w)
            lay.setContentsMargins(4, 3, 4, 3)
            btn = QPushButton("📍 Chốt")
            btn.setObjectName("BtnBlue")
            btn.setFixedHeight(27)
            btn.clicked.connect(lambda _, r=i, k=key: self._capture(r, k))
            lay.addWidget(btn)
            self.tbl.setCellWidget(i, 3, w)

        root.addWidget(self.tbl, 1)

        # Bottom
        bb = QHBoxLayout(); bb.setSpacing(8)
        btn_clear = _btn("🗑 Reset",      "BtnRed",    32)
        btn_test  = _btn("▶ Test click", "BtnGray",   32)
        btn_save  = _btn("💾 Lưu",       "BtnStart",  36)
        btn_close = _btn("Đóng",          "BtnGray",   32)

        btn_clear.setToolTip("Xóa tất cả tọa độ đã lưu")
        btn_test.setToolTip("Click thử vào tọa độ đầu tiên để kiểm tra")
        btn_save.setFont(QFont("Segoe UI", 11, QFont.Bold))

        btn_clear.clicked.connect(self._reset_all)
        btn_test.clicked.connect(self._test_click)
        btn_save.clicked.connect(self._save_and_close)
        btn_close.clicked.connect(self.reject)

        bb.addWidget(btn_clear)
        bb.addWidget(btn_test)
        bb.addStretch()
        bb.addWidget(btn_close)
        bb.addWidget(btn_save)
        root.addLayout(bb)

    # ─────────────────────────────────────────────────────────────
    def _tick(self):
        if HAS_PG:
            x, y = pg.position()
            self.lbl_pos.setText(f"({x},  {y})")

    def _capture(self, row: int, key: str):
        if not HAS_PG: return
        x, y = pg.position()
        self._coords[key] = [x, y]

        it = self.tbl.item(row, 2)
        if it:
            it.setText(f"({x}, {y})")

        # Highlight xanh lá
        for col in range(3):
            item = self.tbl.item(row, col)
            if item:
                item.setBackground(QColor("#1a4a2e"))
                item.setForeground(QColor("#ffffff"))

    def _reset_all(self):
        self._coords.clear()
        for i in range(len(FIELDS)):
            it = self.tbl.item(i, 2)
            if it: it.setText("—")
            for col in range(3):
                item = self.tbl.item(i, col)
                if item:
                    item.setBackground(QColor("transparent"))

    def _test_click(self):
        """Click thử vào tọa độ email_field để kiểm tra."""
        if not HAS_PG: return
        import time
        from auth.auto_login import _human_click
        coords = self._coords.get("email_field")
        if coords:
            _human_click(int(coords[0]), int(coords[1]))
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Test", "Chưa chốt tọa độ email_field!")

    def _save_and_close(self):
        save_coords(self._coords)
        self.accept()

    def _load(self) -> dict:
        path = Path(COORDS_FILE)
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return DEFAULT_COORDS.copy()

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)