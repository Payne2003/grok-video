from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QTableWidget, QTableWidgetItem, QPushButton, QTextEdit,
    QHeaderView, QAbstractItemView, QSizePolicy
)
from PySide6.QtCore import Qt, QDateTime
from PySide6.QtGui import QFont, QColor
from datetime import datetime


SAMPLE_ACCOUNTS = [
    ("vonjab@bedor.name.ng",  "logged_in", "2026-03-11 ..."),
    ("fuhmaa@botex.name.ng",  "logged_in", "2026-03-11 ..."),
    ("kecseg@bidar.name.ng",  "logged_in", "2026-03-11 ..."),
    ("dikdil@bigix.name.ng",  "logged_in", "2026-03-11 ..."),
    ("jioluo@benal.name.ng",  "logged_in", "2026-03-11 ..."),
]


class LoginPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # ── Stats row ────────────────────────────────────────────
        stats_frame = QFrame()
        stats_frame.setObjectName("PanelCard")
        s_lay = QHBoxLayout(stats_frame)
        s_lay.setContentsMargins(16, 10, 16, 10)

        total_icon = QLabel("📋")
        total_icon.setFont(QFont("Segoe UI Emoji", 14))
        self.lbl_total = QLabel("Total: 5")
        self.lbl_total.setFont(QFont("Segoe UI", 13, QFont.Bold))
        s_lay.addWidget(total_icon)
        s_lay.addWidget(self.lbl_total)
        s_lay.addStretch()

        logged_icon = QLabel("✅")
        logged_icon.setFont(QFont("Segoe UI Emoji", 14))
        self.lbl_logged = QLabel("Logged in: 5")
        self.lbl_logged.setFont(QFont("Segoe UI", 13, QFont.Bold))
        s_lay.addWidget(logged_icon)
        s_lay.addWidget(self.lbl_logged)
        layout.addWidget(stats_frame)

        # ── Account list card ─────────────────────────────────────
        card = QFrame()
        card.setObjectName("PanelCard")
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(14, 12, 14, 14)
        c_lay.setSpacing(10)

        title_row = QHBoxLayout()
        icon = QLabel("📋")
        icon.setFont(QFont("Segoe UI Emoji", 13))
        title = QLabel("Account List")
        title.setObjectName("SectionTitle")
        title_row.addWidget(icon)
        title_row.addSpacing(4)
        title_row.addWidget(title)
        title_row.addStretch()
        c_lay.addLayout(title_row)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["", "Email", "Status", "Last Login", "Error", "Chrome"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 44)
        self.table.setColumnWidth(2, 110)
        self.table.setColumnWidth(3, 130)
        self.table.setColumnWidth(4, 70)
        self.table.setColumnWidth(5, 80)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setMinimumHeight(240)

        self._populate_table()
        c_lay.addWidget(self.table)

        # Buttons row
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)
        btns = [
            ("➕ Add",         "BtnGreen"),
            ("✏️ Edit",         "BtnGray"),
            ("🗑 Delete",       "BtnRed"),
            ("🗑 Xóa tất cả",  "BtnRed"),
            ("✔️ Chon tất cả", "BtnGray"),
            ("🔑 Login",       "BtnBlue"),
            ("🔑 Login All",   "BtnOrange"),
            ("📄 Nhập TXT",    "BtnTeal"),
            ("📤 Export",      "BtnGray"),
            ("📥 Import",      "BtnOrange"),
        ]
        for text, obj in btns:
            b = QPushButton(text)
            b.setObjectName(obj)
            b.setFixedHeight(34)
            btn_layout.addWidget(b)
        btn_layout.addStretch()
        c_lay.addLayout(btn_layout)
        layout.addWidget(card)

        # ── Log area ──────────────────────────────────────────────
        log_card = QFrame()
        log_card.setObjectName("PanelCard")
        log_lay = QVBoxLayout(log_card)
        log_lay.setContentsMargins(14, 10, 14, 10)
        log_lay.setSpacing(6)

        log_title_row = QHBoxLayout()
        log_icon = QLabel("📝")
        log_icon.setFont(QFont("Segoe UI Emoji", 12))
        log_lbl = QLabel("Log")
        log_lbl.setObjectName("SectionTitle")
        log_title_row.addWidget(log_icon)
        log_title_row.addSpacing(4)
        log_title_row.addWidget(log_lbl)
        log_title_row.addStretch()
        log_lay.addLayout(log_title_row)

        self.log_area = QTextEdit()
        self.log_area.setObjectName("LogArea")
        self.log_area.setReadOnly(True)
        self.log_area.setFixedHeight(90)
        log_lay.addWidget(self.log_area)
        layout.addWidget(log_card)

    def _populate_table(self):
        self.table.setRowCount(len(SAMPLE_ACCOUNTS))
        for row, (email, status, last_login) in enumerate(SAMPLE_ACCOUNTS):
            # Row number
            num = QTableWidgetItem(str(row + 1))
            num.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, num)

            # Email
            self.table.setItem(row, 1, QTableWidgetItem(email))

            # Status badge
            status_item = QTableWidgetItem(status)
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setBackground(QColor("#238636"))
            status_item.setForeground(QColor("#ffffff"))
            self.table.setItem(row, 2, status_item)

            # Last login
            ll = QTableWidgetItem(last_login)
            ll.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, ll)

            # Error
            err = QTableWidgetItem("-")
            err.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, err)

            # Chrome button placeholder
            chrome_item = QTableWidgetItem("🔓 Mở")
            chrome_item.setTextAlignment(Qt.AlignCenter)
            chrome_item.setBackground(QColor("#d29922"))
            chrome_item.setForeground(QColor("#ffffff"))
            self.table.setItem(row, 5, chrome_item)

            self.table.setRowHeight(row, 36)
