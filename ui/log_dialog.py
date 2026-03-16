"""
log_dialog.py
Popup fullscreen xem log – mở từ nút "Xem log" hoặc double-click panel nhỏ.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QPlainTextEdit, QLabel, QFileDialog, QSizePolicy, QWidget
)
from PySide6.QtCore import Qt, QDateTime
from PySide6.QtGui import QFont, QTextCursor, QColor, QPalette


class LogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📋 Log chi tiết")
        self.setMinimumSize(780, 520)
        self.resize(900, 600)
        self.setWindowFlags(
            Qt.Dialog |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint |
            Qt.WindowCloseButtonHint
        )
        self._build()

    # ─────────────────────────────────────────────
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("📋  Log chi tiết")
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        hdr.addWidget(title)
        hdr.addStretch()

        self.lbl_count = QLabel("0 dòng")
        self.lbl_count.setObjectName("HintLabel")
        hdr.addWidget(self.lbl_count)
        root.addLayout(hdr)

        # Log view
        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setFont(QFont("Consolas", 10))
        self.view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.view.setObjectName("LogView")
        root.addWidget(self.view, 1)

        # Bottom buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_clear = QPushButton("🗑  Xóa log")
        self.btn_clear.setObjectName("BtnRed")
        self.btn_clear.setFixedHeight(32)
        self.btn_clear.clicked.connect(self._clear)

        self.btn_save = QPushButton("💾  Lưu log")
        self.btn_save.setObjectName("BtnGray")
        self.btn_save.setFixedHeight(32)
        self.btn_save.clicked.connect(self._save)

        self.btn_close = QPushButton("✖  Đóng")
        self.btn_close.setObjectName("BtnGray")
        self.btn_close.setFixedHeight(32)
        self.btn_close.clicked.connect(self.hide)

        for b in (self.btn_clear, self.btn_save, self.btn_close):
            btn_row.addWidget(b)

        root.addLayout(btn_row)

    # ─────────────────────────────────────────────
    def append(self, text: str):
        """Thêm 1 dòng vào log (gọi từ controller, thread-safe qua signal)."""
        self.view.appendPlainText(text)
        # Tự scroll xuống cuối
        cur = self.view.textCursor()
        cur.movePosition(QTextCursor.End)
        self.view.setTextCursor(cur)
        # Cập nhật đếm dòng
        lines = self.view.blockCount()
        self.lbl_count.setText(f"{lines} dòng")

    def get_text(self) -> str:
        return self.view.toPlainText()

    def clear(self):
        self.view.clear()
        self.lbl_count.setText("0 dòng")

    # ─────────────────────────────────────────────
    def _clear(self):
        self.clear()

    def _save(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu log", "generation_log.txt", "Text files (*.txt)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.get_text())