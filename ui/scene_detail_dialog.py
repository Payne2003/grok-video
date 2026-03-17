"""
scene_detail_dialog.py
Dialog khi double-click vào 1 row → chỉ để xem/sửa prompt rồi Save.
Tạo lại và Xem video nằm trực tiếp trên từng dòng bảng.
"""

import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


class SceneDetailDialog(QDialog):

    # Phát khi user bấm "Lưu" — truyền (row, new_prompt)
    prompt_saved = Signal(int, str)

    def __init__(self, row: int, scene_name: str, prompt: str,
                 status: str, parent=None):
        super().__init__(parent)

        self.row        = row
        self.scene_name = scene_name

        self.setWindowTitle(f"Chỉnh sửa prompt — {scene_name}")
        self.setMinimumWidth(580)
        self.setMinimumHeight(320)
        self.setWindowFlags(
            Qt.Dialog |
            Qt.WindowCloseButtonHint |
            Qt.WindowMaximizeButtonHint
        )
        self._build(prompt, status)

    def _build(self, prompt: str, status: str):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # ── Header ────────────────────────────────────────────────
        hdr = QHBoxLayout()
        name_lbl = QLabel(f"🎬  {self.scene_name}")
        name_lbl.setFont(QFont("Segoe UI", 13, QFont.Bold))
        hdr.addWidget(name_lbl)
        hdr.addStretch()
        self.lbl_status = QLabel(status)
        self.lbl_status.setObjectName("HintLabel")
        hdr.addWidget(self.lbl_status)
        root.addLayout(hdr)

        line = QFrame(); line.setFrameShape(QFrame.HLine)
        line.setObjectName("Divider")
        root.addWidget(line)

        # ── Prompt editor ─────────────────────────────────────────
        root.addWidget(QLabel("📝  Prompt (có thể chỉnh sửa rồi Lưu)"))

        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlainText(prompt)
        self.prompt_edit.setFont(QFont("Segoe UI", 10))
        self.prompt_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root.addWidget(self.prompt_edit, 1)

        # ── Buttons ───────────────────────────────────────────────
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        btn_row.addStretch()

        btn_cancel = QPushButton("Đóng")
        btn_cancel.setObjectName("BtnGray")
        btn_cancel.setFixedHeight(34)
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("💾  Lưu prompt")
        btn_save.setObjectName("BtnStart")
        btn_save.setFixedHeight(34)
        btn_save.setFont(QFont("Segoe UI", 11, QFont.Bold))
        btn_save.clicked.connect(self._save)

        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        root.addLayout(btn_row)

    def _save(self):
        new_prompt = self.prompt_edit.toPlainText().strip()
        if not new_prompt:
            return
        self.prompt_saved.emit(self.row, new_prompt)
        self.accept()