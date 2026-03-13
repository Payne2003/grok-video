from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

class HistoryPanel(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(12)
        ico = QLabel("📋")
        ico.setFont(QFont("Segoe UI Emoji", 48))
        ico.setAlignment(Qt.AlignCenter)
        t = QLabel("Lịch sử")
        t.setObjectName("SectionTitle")
        t.setAlignment(Qt.AlignCenter)
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        d = QLabel("Xem lại toàn bộ lịch sử tạo video và ảnh")
        d.setAlignment(Qt.AlignCenter)
        lay.addWidget(ico)
        lay.addWidget(t)
        lay.addWidget(d)
