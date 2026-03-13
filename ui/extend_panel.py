from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class ExtendPanel(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(12)

        ico = QLabel("🔗")
        ico.setFont(QFont("Segoe UI Emoji", 48))
        ico.setAlignment(Qt.AlignCenter)

        t = QLabel("Extend Video")
        t.setObjectName("SectionTitle")
        t.setAlignment(Qt.AlignCenter)
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))

        d = QLabel("Kéo dài video hiện có với Grok AI")
        d.setObjectName("StatLabel")
        d.setAlignment(Qt.AlignCenter)
        d.setFont(QFont("Segoe UI", 12))

        lay.addWidget(ico)
        lay.addWidget(t)
        lay.addWidget(d)
