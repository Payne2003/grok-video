from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

class ImagePanel(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(12)
        ico = QLabel("🖼️")
        ico.setFont(QFont("Segoe UI Emoji", 48))
        ico.setAlignment(Qt.AlignCenter)
        t = QLabel("Tạo Ảnh")
        t.setObjectName("SectionTitle")
        t.setAlignment(Qt.AlignCenter)
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        d = QLabel("Tính năng tạo ảnh từ văn bản bằng Grok AI")
        d.setAlignment(Qt.AlignCenter)
        lay.addWidget(ico)
        lay.addWidget(t)
        lay.addWidget(d)
