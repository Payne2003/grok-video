from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QPushButton, QTextEdit, QLineEdit, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QComboBox, QFileDialog,
    QScrollArea, QSizePolicy, QPlainTextEdit
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QTextCursor


# ─────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────

def _btn(text, obj, h=32, w=None):
    b = QPushButton(text)
    b.setObjectName(obj)
    b.setFixedHeight(h)
    b.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
    if w:
        b.setFixedWidth(w)
    return b


class StatBox(QFrame):
    def __init__(self, label, frame_obj, num_obj):
        super().__init__()
        self.setObjectName(frame_obj)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumWidth(80)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 10, 8, 10)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(2)

        self.num = QLabel("0")
        self.num.setObjectName(num_obj)
        self.num.setAlignment(Qt.AlignCenter)
        self.num.setFont(QFont("Segoe UI", 28, QFont.Black))

        self.lbl = QLabel(label)
        self.lbl.setObjectName("StatLabel")
        self.lbl.setAlignment(Qt.AlignCenter)

        lay.addWidget(self.num)
        lay.addWidget(self.lbl)

    def set_value(self, v):
        self.num.setText(str(v))


# ─────────────────────────────────────────────────────────────────
#  COLLAPSIBLE LOG PANEL
# ─────────────────────────────────────────────────────────────────

class LogPanel(QFrame):
    """
    Panel log nhỏ nằm dưới table.
    - Click header để thu/mở.
    - Nút ⛶ để mở popup fullscreen (signal → controller).
    """
    open_fullscreen = Signal()

    _COLLAPSED_H = 32
    _EXPANDED_H  = 180

    def __init__(self):
        super().__init__()
        self.setObjectName("LogPanel")
        self._expanded = False
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── Header bar ────────────────────────────────────────────
        self._header = QFrame()
        self._header.setObjectName("LogPanelHeader")
        self._header.setFixedHeight(self._COLLAPSED_H)
        self._header.setCursor(Qt.PointingHandCursor)

        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(10, 0, 6, 0)
        hl.setSpacing(6)

        self._arrow = QLabel("▶")
        self._arrow.setObjectName("LogArrow")
        self._arrow.setFixedWidth(14)

        title_lbl = QLabel("Log")
        title_lbl.setObjectName("LogTitle")

        self.lbl_preview = QLabel("—")
        self.lbl_preview.setObjectName("LogLastLine")
        self.lbl_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.lbl_preview.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        self._btn_popup = _btn("⛶", "BtnGray", 24, 28)
        self._btn_popup.setToolTip("Mở fullscreen")
        self._btn_popup.clicked.connect(self.open_fullscreen.emit)

        hl.addWidget(self._arrow)
        hl.addWidget(title_lbl)
        hl.addSpacing(8)
        hl.addWidget(self.lbl_preview, 1)
        hl.addWidget(self._btn_popup)

        # click header = toggle (tránh click nút popup bị bắt 2 lần)
        self._header.mousePressEvent = self._header_clicked

        lay.addWidget(self._header)

        # ── Log text ──────────────────────────────────────────────
        self._view = QPlainTextEdit()
        self._view.setReadOnly(True)
        self._view.setFont(QFont("Consolas", 9))
        self._view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._view.setObjectName("LogMiniView")
        self._view.setFixedHeight(self._EXPANDED_H - self._COLLAPSED_H)
        self._view.hide()
        lay.addWidget(self._view)

        self.setFixedHeight(self._COLLAPSED_H)

    def _header_clicked(self, event):
        # Bỏ qua nếu click vào nút popup
        if self._btn_popup.underMouse():
            return
        self._toggle()

    def _toggle(self):
        self._expanded = not self._expanded
        self._arrow.setText("▼" if self._expanded else "▶")
        if self._expanded:
            self._view.show()
            self.setFixedHeight(self._EXPANDED_H)
        else:
            self._view.hide()
            self.setFixedHeight(self._COLLAPSED_H)

    # ── Public API (gọi từ controller) ────────────────────────────
    def append(self, text: str):
        self._view.appendPlainText(text)
        cur = self._view.textCursor()
        cur.movePosition(QTextCursor.End)
        self._view.setTextCursor(cur)
        # Preview trên header (80 ký tự)
        short = text[:80] + ("…" if len(text) > 80 else "")
        self.lbl_preview.setText(short)

    def clear(self):
        self._view.clear()
        self.lbl_preview.setText("—")

    def get_text(self) -> str:
        return self._view.toPlainText()


# ─────────────────────────────────────────────────────────────────
#  MAIN PANEL
# ─────────────────────────────────────────────────────────────────

class GeneratorPanel(QWidget):
    MODE_TEXT  = "text"
    MODE_IMAGE = "image"

    # Signals – KHÔNG kết nối trong UI, controller đảm nhiệm toàn bộ
    start_clicked         = Signal()
    import_txt_clicked    = Signal()
    import_folder_clicked = Signal()

    def __init__(self):
        super().__init__()
        self._mode = self.MODE_TEXT
        self.setMinimumWidth(800)
        self._build()

    # ═══════════════════════════════════════════════════════════════
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Stats row ─────────────────────────────────────────────
        stat_row = QWidget()
        stat_row.setObjectName("StatRow")
        stat_row.setFixedHeight(90)
        sr = QHBoxLayout(stat_row)
        sr.setContentsMargins(12, 8, 12, 8)
        sr.setSpacing(8)
        self.s_total   = StatBox("Tổng",      "StatTotal",   "StatNumTotal")
        self.s_running = StatBox("Đang chạy", "StatRunning", "StatNumRunning")
        self.s_done    = StatBox("Xong",       "StatDone",    "StatNumDone")
        self.s_error   = StatBox("Lỗi",        "StatError",   "StatNumError")
        for s in (self.s_total, self.s_running, self.s_done, self.s_error):
            sr.addWidget(s)
        root.addWidget(stat_row)

        # ── Status bar ────────────────────────────────────────────
        status_bar = QFrame()
        status_bar.setObjectName("StatusBar")
        status_bar.setFixedHeight(32)
        sbl = QHBoxLayout(status_bar)
        sbl.setContentsMargins(14, 0, 14, 0)
        sbl.setSpacing(8)
        self.lbl_status_icon = QLabel("✅")
        sbl.addWidget(self.lbl_status_icon)
        self.lbl_status = QLabel("Sẵn sàng")
        self.lbl_status.setObjectName("StatusLabel")
        sbl.addWidget(self.lbl_status)
        sbl.addStretch()
        root.addWidget(status_bar)

        # ── Splitter ──────────────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_left_scroll())
        splitter.addWidget(self._build_right_panel())
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([420, 580])
        root.addWidget(splitter, 1)

    # ─────────────────── LEFT ─────────────────────────────────────

    def _build_left_scroll(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setObjectName("LeftScroll")

        inner = QWidget()
        inner.setObjectName("LeftInner")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        # Mode toggle
        mode_card = QFrame(); mode_card.setObjectName("Card")
        ml = QHBoxLayout(mode_card)
        ml.setContentsMargins(10, 8, 10, 8); ml.setSpacing(8)
        self.btn_text  = _btn("📄  Text → Video",  "TabToggle",    36)
        self.btn_image = _btn("🖼️  Image → Video", "TabToggleOff", 36)
        self.btn_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_image.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        ml.addWidget(self.btn_text); ml.addWidget(self.btn_image)
        lay.addWidget(mode_card)

        # Prompt card (TEXT mode)
        self.prompt_card = QFrame(); self.prompt_card.setObjectName("Card")
        pl = QVBoxLayout(self.prompt_card)
        pl.setContentsMargins(12, 10, 12, 12); pl.setSpacing(8)
        ph = QHBoxLayout()
        pi = QLabel("📝"); pi.setFont(QFont("Segoe UI Emoji", 11))
        pt_lbl = QLabel("Prompts"); pt_lbl.setObjectName("CardTitle")
        ph.addWidget(pi); ph.addSpacing(4); ph.addWidget(pt_lbl); ph.addStretch()
        pl.addLayout(ph)
        self.prompt = QTextEdit()
        self.prompt.setPlaceholderText("Nhập prompt (mỗi dòng 1 prompt)...")
        self.prompt.setMinimumHeight(140)
        self.prompt.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        pl.addWidget(self.prompt)
        fb = QHBoxLayout(); fb.setSpacing(6)
        self.btn_import_txt = _btn("📄 Nhập TXT", "BtnGray", 30)
        self.btn_clear      = _btn("🗑 Xóa",      "BtnRed",  30)
        self.btn_import_txt.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_clear.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        fb.addWidget(self.btn_import_txt); fb.addWidget(self.btn_clear)
        pl.addLayout(fb)
        lay.addWidget(self.prompt_card)

        # Image card (IMAGE mode)
        self.image_card = QFrame(); self.image_card.setObjectName("Card")
        il = QVBoxLayout(self.image_card)
        il.setContentsMargins(12, 10, 12, 12); il.setSpacing(8)
        ih = QHBoxLayout()
        ii = QLabel("🖼️"); ii.setFont(QFont("Segoe UI Emoji", 11))
        it_lbl = QLabel("Thư mục scenes"); it_lbl.setObjectName("CardTitle")
        ih.addWidget(ii); ih.addSpacing(4); ih.addWidget(it_lbl); ih.addStretch()
        il.addLayout(ih)
        hint = QLabel("Chọn thư mục cha chứa các subfolder scene:")
        hint.setObjectName("HintLabel"); il.addWidget(hint)
        hint2 = QLabel("📁 scenes/\n   ├─ 📁 scene_01/\n   ├─ 📁 scene_02/\n   └─ 📁 scene_03/ ...")
        hint2.setObjectName("CodeHint"); il.addWidget(hint2)
        self.btn_import_folder = _btn("📁 Chọn thư mục scenes", "BtnBlue", 36)
        self.btn_import_folder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        il.addWidget(self.btn_import_folder)
        self.lbl_image_count = QLabel("Chưa chọn thư mục")
        self.lbl_image_count.setObjectName("HintLabel")
        self.lbl_image_count.setWordWrap(True); il.addWidget(self.lbl_image_count)
        self.scene_table = QTableWidget()
        self.scene_table.setColumnCount(3)
        self.scene_table.setHorizontalHeaderLabels(["#", "Scene", "Ảnh"])
        _sh = self.scene_table.horizontalHeader()
        _sh.setSectionResizeMode(0, QHeaderView.Fixed)
        _sh.setSectionResizeMode(1, QHeaderView.Stretch)
        _sh.setSectionResizeMode(2, QHeaderView.Fixed)
        self.scene_table.setColumnWidth(0, 36)
        self.scene_table.setColumnWidth(2, 54)
        self.scene_table.verticalHeader().setVisible(False)
        self.scene_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.scene_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.scene_table.setFrameShape(QFrame.NoFrame)
        self.scene_table.setFixedHeight(160)
        self.scene_table.hide(); il.addWidget(self.scene_table)
        self.image_card.hide(); lay.addWidget(self.image_card)

        # Output card
        out_card = QFrame(); out_card.setObjectName("Card")
        ol = QVBoxLayout(out_card)
        ol.setContentsMargins(12, 10, 12, 12); ol.setSpacing(8)
        oh = QHBoxLayout()
        oi = QLabel("📁"); oi.setFont(QFont("Segoe UI Emoji", 11))
        ot_lbl = QLabel("Thư mục xuất"); ot_lbl.setObjectName("CardTitle")
        oh.addWidget(oi); oh.addSpacing(4); oh.addWidget(ot_lbl); oh.addStretch()
        ol.addLayout(oh)
        or_ = QHBoxLayout(); or_.setSpacing(6)
        self.out_path = QLineEdit("D:\\GrokVideoGenerator1103\\output")
        self.out_path.setFixedHeight(32)
        self.out_path.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_browse = _btn("...", "BtnGray", 32, 36)
        or_.addWidget(self.out_path); or_.addWidget(self.btn_browse)
        ol.addLayout(or_); lay.addWidget(out_card)

        # Settings card
        set_card = QFrame(); set_card.setObjectName("Card")
        sl = QVBoxLayout(set_card)
        sl.setContentsMargins(12, 10, 12, 12); sl.setSpacing(8)
        sh = QHBoxLayout()
        si = QLabel("⚙️"); si.setFont(QFont("Segoe UI Emoji", 11))
        st_lbl = QLabel("Cài đặt"); st_lbl.setObjectName("CardTitle")
        sh.addWidget(si); sh.addSpacing(4); sh.addWidget(st_lbl); sh.addStretch()
        sl.addLayout(sh)
        self.combos = {}
        for key, label, default, options in [
            ("ratio",    "Tỷ lệ:",      "16:9",   ["16:9", "9:16", "1:1", "4:3"]),
            ("duration", "Thời lượng:", "6 giây", ["5 giây", "6 giây", "8 giây", "10 giây"]),
            ("quality",  "Phân giải:",  "720p",   ["480p", "720p", "1080p"]),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(label); lbl.setFixedWidth(85); lbl.setObjectName("SettingLabel")
            cb = QComboBox(); cb.addItems(options); cb.setCurrentText(default)
            cb.setFixedHeight(30); cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.combos[key] = cb
            row.addWidget(lbl); row.addWidget(cb); sl.addLayout(row)
        lay.addWidget(set_card)

        # Start button
        self.btn_start = _btn("▶  Bắt đầu tạo video", "BtnStart", 44)
        self.btn_start.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_start.setFont(QFont("Segoe UI", 13, QFont.Bold))
        lay.addWidget(self.btn_start)

        lay.addStretch()
        scroll.setWidget(inner)
        return scroll

    # ─────────────────── RIGHT panel ──────────────────────────────

    def _build_right_panel(self):
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(8, 12, 12, 12)
        lay.setSpacing(6)

        # Main table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["#", "Prompt / File", "Trạng thái"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 40)
        self.table.setColumnWidth(2, 110)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setRowCount(0)
        self.table.setFrameShape(QFrame.NoFrame)
        self.table.setMinimumHeight(200)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay.addWidget(self.table, 1)

        # Action buttons
        ab = QHBoxLayout(); ab.setSpacing(6); ab.addStretch()
        self.btn_retry_errors = _btn("🔄 Chạy Lại Lỗi", "BtnGray", 32)
        self.btn_retry_all    = _btn("📋 Tạo Lại All",   "BtnGray", 32)
        self.btn_retry_one    = _btn("▶️ Tạo Lại",       "BtnBlue", 32)
        for b in (self.btn_retry_errors, self.btn_retry_all, self.btn_retry_one):
            ab.addWidget(b)
        lay.addLayout(ab)

        # ── Log panel nhỏ (thu gọn / mở rộng) ────────────────────
        self.log_panel = LogPanel()
        lay.addWidget(self.log_panel)

        # Xem log fullscreen
        lb = QHBoxLayout(); lb.addStretch()
        self.btn_view_log = _btn("📋 Xem log", "BtnGray", 32)
        lb.addWidget(self.btn_view_log)
        lay.addLayout(lb)

        return container