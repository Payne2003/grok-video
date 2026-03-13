from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QPushButton, QTextEdit, QLineEdit, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QComboBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


def _btn(text, obj, h=30, w=None):
    b = QPushButton(text)
    b.setObjectName(obj)
    b.setFixedHeight(h)
    if w:
        b.setFixedWidth(w)
    return b


class StatBox(QFrame):
    """Coloured stat card with big number + label."""
    def __init__(self, label, value="0", frame_obj="StatTotal", num_obj="StatNumTotal"):
        super().__init__()
        self.setObjectName(frame_obj)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 14, 12, 14)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(4)

        self.num = QLabel(str(value))
        self.num.setObjectName(num_obj)
        self.num.setAlignment(Qt.AlignCenter)
        self.num.setFont(QFont("Segoe UI", 36, QFont.Black))

        self.lbl = QLabel(label)
        self.lbl.setObjectName("StatLabel")
        self.lbl.setAlignment(Qt.AlignCenter)

        lay.addWidget(self.num)
        lay.addWidget(self.lbl)

    def set_value(self, v): self.num.setText(str(v))


class GeneratorPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # ── Stat boxes ───────────────────────────────────────────
        sr = QHBoxLayout()
        sr.setSpacing(10)
        self.s_total   = StatBox("Tổng",       "0", "StatTotal",   "StatNumTotal")
        self.s_running = StatBox("Đang chạy",  "0", "StatRunning", "StatNumRunning")
        self.s_done    = StatBox("Xong",        "0", "StatDone",    "StatNumDone")
        self.s_error   = StatBox("Lỗi",         "0", "StatError",   "StatNumError")
        for w in (self.s_total, self.s_running, self.s_done, self.s_error):
            sr.addWidget(w)
        root.addLayout(sr)

        # ── Ready bar ─────────────────────────────────────────────
        rb = QFrame()
        rb.setObjectName("ReadyBar")
        rb.setFixedHeight(34)
        rbl = QHBoxLayout(rb)
        rbl.setContentsMargins(14, 0, 14, 0)
        rbl.addWidget(QLabel("✅"))
        lbl = QLabel("Sẵn sàng")
        lbl.setObjectName("ReadyLabel")
        rbl.addSpacing(6)
        rbl.addWidget(lbl)
        rbl.addStretch()
        root.addWidget(rb)

        # ── Splitter ──────────────────────────────────────────────
        sp = QSplitter(Qt.Horizontal)
        sp.setHandleWidth(1)
        sp.addWidget(self._left())
        sp.addWidget(self._right())
        sp.setStretchFactor(0, 2)
        sp.setStretchFactor(1, 3)
        root.addWidget(sp, 1)

    # ─────────────────────────── LEFT PANEL ──────────────────────
    def _left(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 8, 0)
        lay.setSpacing(10)

        # Mode toggle
        mr = QHBoxLayout()
        mr.setSpacing(6)
        self.btn_text  = _btn("📄  Text → Video",  "TabToggle",    34)
        self.btn_image = _btn("🖼️  Image → Video", "TabToggleOff", 34)
        mr.addWidget(self.btn_text)
        mr.addWidget(self.btn_image)
        mr.addStretch()
        lay.addLayout(mr)

        # Prompt card
        pc = QFrame()
        pc.setObjectName("PanelCard")
        pl = QVBoxLayout(pc)
        pl.setContentsMargins(14, 12, 14, 14)
        pl.setSpacing(10)

        pt = QHBoxLayout()
        pi = QLabel("📝")
        pi.setFont(QFont("Segoe UI Emoji", 12))
        pt_lbl = QLabel("Prompts")
        pt_lbl.setObjectName("SectionTitle")
        pt.addWidget(pi); pt.addSpacing(6); pt.addWidget(pt_lbl); pt.addStretch()
        pl.addLayout(pt)

        self.prompt = QTextEdit()
        self.prompt.setPlaceholderText("Nhập prompt (mỗi dòng 1 prompt)...")
        self.prompt.setMinimumHeight(150)
        pl.addWidget(self.prompt)

        # File buttons
        fb = QHBoxLayout()
        fb.setSpacing(6)
        fb.addWidget(_btn("📄 Nhập TXT",    "BtnGray", 30))
        fb.addWidget(_btn("📁 Nhập Folder", "BtnGray", 30))
        fb.addWidget(_btn("🗑 Xóa",         "BtnRed",  30))
        fb.addStretch()
        pl.addLayout(fb)

        # Output folder
        ol = QLabel("📁  Thư mục xuất:")
        pl.addWidget(ol)
        or_ = QHBoxLayout()
        self.out_path = QLineEdit("D:\\GrokVideoGenerator1103\\output")
        self.out_path.setFixedHeight(32)
        bb = _btn("...", "BtnGray", 32, 32)
        or_.addWidget(self.out_path)
        or_.addWidget(bb)
        pl.addLayout(or_)
        lay.addWidget(pc)

        # Settings card
        sc = QFrame()
        sc.setObjectName("PanelCard")
        sl = QVBoxLayout(sc)
        sl.setContentsMargins(14, 12, 14, 14)
        sl.setSpacing(10)

        st = QHBoxLayout()
        si = QLabel("⚙️")
        si.setFont(QFont("Segoe UI Emoji", 12))
        s_lbl = QLabel("Cài đặt")
        s_lbl.setObjectName("SectionTitle")
        st.addWidget(si); st.addSpacing(6); st.addWidget(s_lbl); st.addStretch()
        sl.addLayout(st)

        for label, default, options in [
            ("Tỷ lệ:",      "16:9",   ["16:9", "9:16", "1:1", "4:3"]),
            ("Thời lượng:", "6 giây", ["5 giây", "6 giây", "8 giây", "10 giây"]),
            ("Phân giải:",  "720p",   ["480p", "720p", "1080p"]),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setFixedWidth(90)
            cb = QComboBox()
            cb.addItems(options)
            cb.setCurrentText(default)
            cb.setFixedHeight(30)
            row.addWidget(lbl)
            row.addWidget(cb)
            sl.addLayout(row)

        lay.addWidget(sc)
        lay.addStretch()
        return w

    # ─────────────────────────── RIGHT PANEL ─────────────────────
    def _right(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 0, 0, 0)
        lay.setSpacing(8)

        # Filter row 1
        f1 = QHBoxLayout()
        f1.setSpacing(6)
        f1.addWidget(_btn("📋 Hàng đợi",  "TabToggle",    32))
        f1.addWidget(_btn("▶️ Đang chạy", "TabToggleOff", 32))
        f1.addWidget(_btn("✅ Hoàn thành","TabToggleOff", 32))
        f1.addStretch()
        lay.addLayout(f1)

        # Filter row 2
        f2 = QHBoxLayout()
        f2.setSpacing(6)
        f2.addWidget(_btn("Tất cả",      "TabToggle",    28))
        f2.addWidget(_btn("▶️ Đang chạy","TabToggleOff", 28))
        f2.addWidget(_btn("❌ Lỗi",       "BtnRed",       28))
        f2.addWidget(_btn("✅ Xong",      "TabToggleOff", 28))
        f2.addStretch()
        lay.addLayout(f2)

        # Queue table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["#", "Prompt", "Trạng thái"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 44)
        self.table.setColumnWidth(2, 120)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setRowCount(0)
        self.table.setFrameShape(QFrame.NoFrame)
        lay.addWidget(self.table, 1)

        # Bottom action buttons
        ab = QHBoxLayout()
        ab.setSpacing(6)
        ab.addStretch()
        ab.addWidget(_btn("🔄 Chạy Lại Lỗi", "BtnGray",   32))
        ab.addWidget(_btn("📋 Tạo Lại All",   "BtnGray",   32))
        ab.addWidget(_btn("▶️ Tạo Lại",       "BtnBlue",   32))
        lay.addLayout(ab)

        lb = QHBoxLayout()
        lb.addStretch()
        lb.addWidget(_btn("📋 Xem log", "BtnGray", 32))
        lay.addLayout(lb)

        return w
