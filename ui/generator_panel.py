from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QPushButton, QTextEdit, QLineEdit, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QComboBox, QSizePolicy, QScrollArea
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QColor


class StatBox(QFrame):
    def __init__(self, label, value="0", obj_name="StatTotal", num_obj="StatNumTotal"):
        super().__init__()
        self.setObjectName(obj_name)
        self.setMinimumHeight(90)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setAlignment(Qt.AlignCenter)

        self.num_lbl = QLabel(str(value))
        self.num_lbl.setObjectName(num_obj)
        self.num_lbl.setAlignment(Qt.AlignCenter)
        self.num_lbl.setFont(QFont("Segoe UI", 30, QFont.Bold))

        self.lbl = QLabel(label)
        self.lbl.setObjectName("StatLabel")
        self.lbl.setAlignment(Qt.AlignCenter)
        self.lbl.setFont(QFont("Segoe UI", 11))

        lay.addWidget(self.num_lbl)
        lay.addWidget(self.lbl)

    def set_value(self, v):
        self.num_lbl.setText(str(v))


class GeneratorPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(12)

        # ── Stat boxes ───────────────────────────────────────────
        stats_row = QHBoxLayout()
        stats_row.setSpacing(8)
        self.stat_total   = StatBox("Tổng",       "0", "StatTotal",   "StatNumTotal")
        self.stat_running = StatBox("Đang chạy",  "0", "StatRunning", "StatNumRunning")
        self.stat_done    = StatBox("Xong",        "0", "StatDone",    "StatNumDone")
        self.stat_error   = StatBox("Lỗi",         "0", "StatError",   "StatNumError")
        for w in (self.stat_total, self.stat_running, self.stat_done, self.stat_error):
            stats_row.addWidget(w)
        root.addLayout(stats_row)

        # ── Ready bar ─────────────────────────────────────────────
        ready_bar = QFrame()
        ready_bar.setObjectName("ReadyBar")
        ready_bar.setFixedHeight(32)
        rb_lay = QHBoxLayout(ready_bar)
        rb_lay.setContentsMargins(12, 0, 12, 0)
        rb_icon = QLabel("✅")
        rb_icon.setFont(QFont("Segoe UI Emoji", 11))
        rb_lbl = QLabel("Sẵn sàng")
        rb_lbl.setObjectName("ReadyLabel")
        rb_lay.addWidget(rb_icon)
        rb_lay.addSpacing(4)
        rb_lay.addWidget(rb_lbl)
        rb_lay.addStretch()
        root.addWidget(ready_bar)

        # ── Main splitter ─────────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)

        # LEFT panel
        left = self._build_left()
        splitter.addWidget(left)

        # RIGHT panel
        right = self._build_right()
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)

    def _build_left(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(8)

        # Mode toggle
        mode_row = QHBoxLayout()
        mode_row.setSpacing(0)
        self.btn_text_mode  = QPushButton("📄  Text → Video")
        self.btn_text_mode.setObjectName("TabToggle")
        self.btn_text_mode.setFixedHeight(34)
        self.btn_image_mode = QPushButton("🖼️  Image → Video")
        self.btn_image_mode.setObjectName("TabToggleOff")
        self.btn_image_mode.setFixedHeight(34)
        mode_row.addWidget(self.btn_text_mode)
        mode_row.addSpacing(4)
        mode_row.addWidget(self.btn_image_mode)
        mode_row.addStretch()
        lay.addLayout(mode_row)

        # Prompt card
        prompt_card = QFrame()
        prompt_card.setObjectName("PanelCard")
        p_lay = QVBoxLayout(prompt_card)
        p_lay.setContentsMargins(14, 12, 14, 12)
        p_lay.setSpacing(10)

        pt_row = QHBoxLayout()
        pt_icon = QLabel("📝")
        pt_icon.setFont(QFont("Segoe UI Emoji", 12))
        pt_lbl = QLabel("Prompts")
        pt_lbl.setObjectName("SectionTitle")
        pt_row.addWidget(pt_icon)
        pt_row.addSpacing(4)
        pt_row.addWidget(pt_lbl)
        pt_row.addStretch()
        p_lay.addLayout(pt_row)

        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("Nhập prompt (mỗi dòng 1 prompt)...")
        self.prompt_input.setMinimumHeight(160)
        p_lay.addWidget(self.prompt_input)

        # File buttons
        file_row = QHBoxLayout()
        file_row.setSpacing(6)
        for text, obj in [("📄 Nhập TXT", "BtnGray"), ("📁 Nhập Folder", "BtnGray"), ("🗑 Xóa", "BtnRed")]:
            b = QPushButton(text)
            b.setObjectName(obj)
            b.setFixedHeight(30)
            file_row.addWidget(b)
        file_row.addStretch()
        p_lay.addLayout(file_row)

        # Output folder
        out_lbl = QLabel("📁  Thư mục xuất:")
        out_lbl.setFont(QFont("Segoe UI", 11))
        p_lay.addWidget(out_lbl)

        out_row = QHBoxLayout()
        self.output_path = QLineEdit("D:\\GrokVideoGenerator1103\\output")
        self.output_path.setFixedHeight(30)
        out_row.addWidget(self.output_path)
        browse_btn = QPushButton("...")
        browse_btn.setFixedSize(30, 30)
        browse_btn.setObjectName("BtnGray")
        out_row.addWidget(browse_btn)
        p_lay.addLayout(out_row)

        lay.addWidget(prompt_card)

        # Settings card
        settings_card = QFrame()
        settings_card.setObjectName("PanelCard")
        s_lay = QVBoxLayout(settings_card)
        s_lay.setContentsMargins(14, 12, 14, 12)
        s_lay.setSpacing(10)

        st_row = QHBoxLayout()
        st_icon = QLabel("⚙️")
        st_icon.setFont(QFont("Segoe UI Emoji", 12))
        st_lbl = QLabel("Cài đặt")
        st_lbl.setObjectName("SectionTitle")
        st_row.addWidget(st_icon)
        st_row.addSpacing(4)
        st_row.addWidget(st_lbl)
        st_row.addStretch()
        s_lay.addLayout(st_row)

        fields = [
            ("Tỷ lệ:",       "16:9",  ["16:9", "9:16", "1:1", "4:3"]),
            ("Thời lượng:",  "6 giây", ["5 giây", "6 giây", "8 giây", "10 giây"]),
            ("Phân giải:",   "720p",   ["480p", "720p", "1080p"]),
        ]
        for label, default, options in fields:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setFixedWidth(100)
            combo = QComboBox()
            combo.addItems(options)
            combo.setCurrentText(default)
            combo.setFixedHeight(28)
            row.addWidget(lbl)
            row.addWidget(combo)
            s_lay.addLayout(row)

        lay.addWidget(settings_card)
        lay.addStretch()
        return w

    def _build_right(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 0, 0, 0)
        lay.setSpacing(6)

        # Filter row 1
        f1 = QHBoxLayout()
        f1.setSpacing(4)
        for text, obj in [("📋 Hàng đợi", "TabToggle"), ("▶️ Đang chạy", "BtnGray"), ("✅ Hoàn thành", "BtnGray")]:
            b = QPushButton(text)
            b.setObjectName(obj)
            b.setFixedHeight(30)
            f1.addWidget(b)
        f1.addStretch()
        lay.addLayout(f1)

        # Filter row 2
        f2 = QHBoxLayout()
        f2.setSpacing(4)
        for text, obj in [("Tất cả", "TabToggle"), ("▶️ Đang chạy", "BtnGray"), ("❌ Lỗi", "BtnRed"), ("✅ Xong", "BtnGray")]:
            b = QPushButton(text)
            b.setObjectName(obj)
            b.setFixedHeight(28)
            f2.addWidget(b)
        f2.addStretch()
        lay.addLayout(f2)

        # Queue table
        self.queue_table = QTableWidget()
        self.queue_table.setColumnCount(3)
        self.queue_table.setHorizontalHeaderLabels(["#", "Prompt", "Trạng thái"])
        self.queue_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.queue_table.setColumnWidth(0, 40)
        self.queue_table.setColumnWidth(2, 110)
        self.queue_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.queue_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.queue_table.verticalHeader().setVisible(False)
        self.queue_table.setRowCount(0)
        lay.addWidget(self.queue_table, 1)

        # Action buttons
        action_row = QHBoxLayout()
        action_row.addStretch()
        for text, obj in [("🔄 Chạy Lại Lỗi", "BtnGray"), ("📋 Tạo Lại All", "BtnGray"), ("▶️ Tạo Lại", "BtnBlue")]:
            b = QPushButton(text)
            b.setObjectName(obj)
            b.setFixedHeight(32)
            action_row.addWidget(b)
        lay.addLayout(action_row)

        log_row = QHBoxLayout()
        log_row.addStretch()
        view_log_btn = QPushButton("📋 Xem log")
        view_log_btn.setObjectName("BtnGray")
        view_log_btn.setFixedHeight(32)
        log_row.addWidget(view_log_btn)
        lay.addLayout(log_row)

        return w
