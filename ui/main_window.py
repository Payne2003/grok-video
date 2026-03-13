from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTabWidget, QLabel, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ui.login_panel import LoginPanel
from ui.generator_panel import GeneratorPanel
from ui.image_panel import ImagePanel
from ui.extend_panel import ExtendPanel
from ui.history_panel import HistoryPanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Grok Video Generator")
        self.setMinimumSize(1200, 780)
        self._dark_mode = True
        self._setup_ui()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ──────────────────────────────────────────────
        header = QFrame()
        header.setObjectName("AppHeader")
        header.setFixedHeight(56)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(18, 0, 18, 0)

        icon_lbl = QLabel("🎬")
        icon_lbl.setFont(QFont("Segoe UI Emoji", 18))
        title_lbl = QLabel("Grok Video Generator")
        title_lbl.setObjectName("AppTitle")
        title_lbl.setFont(QFont("Segoe UI", 15, QFont.Bold))
        ver_lbl = QLabel("  v2.2.0")
        ver_lbl.setObjectName("VerLabel")
        ver_lbl.setFont(QFont("Segoe UI", 10))

        h_layout.addWidget(icon_lbl)
        h_layout.addSpacing(6)
        h_layout.addWidget(title_lbl)
        h_layout.addWidget(ver_lbl)
        h_layout.addStretch()

        self.btn_update = QPushButton("🔄  v2.4.0-test")
        self.btn_update.setObjectName("BtnUpdate")
        self.btn_update.setFixedHeight(34)

        self.btn_dark = QPushButton("🌙  Dark")
        self.btn_dark.setObjectName("BtnDark")
        self.btn_dark.setFixedHeight(34)
        self.btn_dark.setCheckable(True)
        self.btn_dark.setChecked(True)
        self.btn_dark.clicked.connect(self._toggle_theme)

        h_layout.addWidget(self.btn_update)
        h_layout.addSpacing(8)
        h_layout.addWidget(self.btn_dark)
        root.addWidget(header)

        # ── Tabs ────────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setObjectName("MainTabs")
        self.tabs.setDocumentMode(True)

        self.login_panel     = LoginPanel()
        self.generator_panel = GeneratorPanel()
        self.image_panel     = ImagePanel()
        self.extend_panel    = ExtendPanel()
        self.history_panel   = HistoryPanel()

        self.tabs.addTab(self.login_panel,     "👤  Tài khoản")
        self.tabs.addTab(self.generator_panel, "🎬  Tạo Video")
        self.tabs.addTab(self.image_panel,     "🖼️  Tạo Ảnh")
        self.tabs.addTab(self.extend_panel,    "🔗  Extend Video")
        self.tabs.addTab(self.history_panel,   "📋  Lịch sử")

        root.addWidget(self.tabs)
        self._apply_stylesheet()

    def _toggle_theme(self, checked):
        self._dark_mode = checked
        self.btn_dark.setText("🌙  Dark" if checked else "☀️  Light")
        self._apply_stylesheet()

    def _apply_stylesheet(self):
        if self._dark_mode:
            bg         = "#0d1117"
            bg2        = "#161b22"
            bg3        = "#21262d"
            border     = "#30363d"
            text       = "#e6edf3"
            text_dim   = "#8b949e"
            accent     = "#58a6ff"
            accent2    = "#1f6feb"
            green      = "#3fb950"
            green_dk   = "#238636"
            orange     = "#d29922"
            orange_dk  = "#9e6a03"
            red        = "#f85149"
            red_dk     = "#b91c1c"
            purple     = "#bc8cff"
            teal       = "#39d353"
            header_bg  = "#010409"
            tab_bg     = "#010409"   # tab bar background
        else:
            bg         = "#f6f8fa"
            bg2        = "#ffffff"
            bg3        = "#eaeef2"
            border     = "#d0d7de"
            text       = "#1f2328"
            text_dim   = "#656d76"
            accent     = "#0969da"
            accent2    = "#0550ae"
            green      = "#1a7f37"
            green_dk   = "#116329"
            orange     = "#9a6700"
            orange_dk  = "#7d5000"
            red        = "#cf222e"
            red_dk     = "#a40e26"
            purple     = "#8250df"
            teal       = "#1a7f37"
            header_bg  = "#f6f8fa"   # LIGHT: header same as bg
            tab_bg     = "#eaeef2"   # LIGHT: tab bar slightly different

        self.setStyleSheet(f"""
        /* ── Global ── */
        QMainWindow, QWidget {{
            background: {bg};
            color: {text};
            font-family: 'Segoe UI', sans-serif;
            font-size: 13px;
        }}

        /* ── CRITICAL: tất cả label/frame con không có bg riêng ── */
        QLabel {{
            color: {text};
            background: transparent;
        }}
        QFrame {{
            background: transparent;
        }}

        /* ── Header ── */
        QFrame#AppHeader {{
            background: {header_bg};
            border-bottom: 1px solid {border};
        }}
        QLabel#AppTitle {{
            color: {text};
            background: transparent;
            font-size: 15px;
            font-weight: 700;
        }}
        QLabel#VerLabel {{
            color: {text_dim};
            background: transparent;
            font-size: 10px;
        }}

        QPushButton#BtnUpdate {{
            background: {orange};
            color: #ffffff;
            border: 1px solid {orange_dk};
            border-radius: 6px;
            padding: 0 16px;
            font-weight: 700;
            font-size: 12px;
        }}
        QPushButton#BtnUpdate:hover {{ background: {orange_dk}; }}

        QPushButton#BtnDark {{
            background: {bg3};
            color: {text};
            border: 1px solid {border};
            border-radius: 6px;
            padding: 0 16px;
            font-size: 12px;
        }}
        QPushButton#BtnDark:hover {{ background: {border}; }}

        /* ── Tabs ── */
        QTabWidget#MainTabs::pane {{
            border: none;
            background: {bg};
        }}
        /* Tab bar itself (the strip) */
        QTabWidget#MainTabs QTabBar {{
            background: {tab_bg};
            border-bottom: 1px solid {border};
        }}
        QTabWidget#MainTabs QTabBar::tab {{
            background: transparent;
            color: {text_dim};
            border: none;
            border-bottom: 2px solid transparent;
            padding: 10px 22px;
            font-size: 13px;
            font-weight: 500;
            margin-right: 2px;
            min-width: 100px;
        }}
        QTabWidget#MainTabs QTabBar::tab:selected {{
            background: {accent2};
            color: #ffffff;
            border-radius: 4px 4px 0 0;
            font-weight: 700;
        }}
        QTabWidget#MainTabs QTabBar::tab:hover:!selected {{
            background: {bg3};
            color: {text};
            border-radius: 4px 4px 0 0;
        }}
        /* Phần còn thừa bên phải tab bar */
        QTabWidget#MainTabs QTabBar::scroller {{
            background: {tab_bg};
        }}

        /* ── Cards / Panels ── */
        QFrame#PanelCard {{
            background: {bg2};
            border: 1px solid {border};
            border-radius: 8px;
        }}
        QLabel#SectionTitle {{
            color: {text};
            background: transparent;
            font-size: 14px;
            font-weight: 700;
        }}

        /* ── Stat Boxes ── */
        QFrame#StatTotal   {{ background: {bg2}; border: 2px solid {accent};  border-radius: 8px; }}
        QFrame#StatRunning {{ background: {bg2}; border: 2px solid {orange};  border-radius: 8px; }}
        QFrame#StatDone    {{ background: {bg2}; border: 2px solid {green};   border-radius: 8px; }}
        QFrame#StatError   {{ background: {bg2}; border: 2px solid {red};     border-radius: 8px; }}

        QLabel#StatNumTotal   {{ color: {accent};  background: transparent; font-size: 38px; font-weight: 800; }}
        QLabel#StatNumRunning {{ color: {orange};  background: transparent; font-size: 38px; font-weight: 800; }}
        QLabel#StatNumDone    {{ color: {green};   background: transparent; font-size: 38px; font-weight: 800; }}
        QLabel#StatNumError   {{ color: {red};     background: transparent; font-size: 38px; font-weight: 800; }}
        QLabel#StatLabel      {{ color: {text_dim}; background: transparent; font-size: 12px; font-weight: 500; }}

        /* ── Table ── */
        QTableWidget {{
            background: {bg2};
            border: 1px solid {border};
            border-radius: 6px;
            gridline-color: {border};
            color: {text};
            selection-background-color: {accent2};
            outline: none;
        }}
        QTableWidget::item {{ padding: 6px 10px; border: none; }}
        QTableWidget::item:selected {{ background: {accent2}; color: #fff; }}
        QTableWidget::item:hover:!selected {{ background: {bg3}; }}
        QHeaderView::section {{
            background: {bg3};
            color: {text_dim};
            border: none;
            border-bottom: 2px solid {border};
            border-right: 1px solid {border};
            padding: 7px 10px;
            font-weight: 700;
            font-size: 12px;
        }}
        QTableCornerButton::section {{ background: {bg3}; border: none; }}

        /* ── Buttons base ── */
        QPushButton {{
            border-radius: 6px;
            padding: 5px 14px;
            font-size: 12px;
            font-weight: 600;
            border: 1px solid transparent;
            min-height: 28px;
            background: transparent;
        }}
        QPushButton#BtnGreen  {{ background: #238636; color: #fff; border-color: #196127; }}
        QPushButton#BtnGreen:hover  {{ background: #2ea043; }}
        QPushButton#BtnBlue   {{ background: {accent2}; color: #fff; border-color: #1158b0; }}
        QPushButton#BtnBlue:hover   {{ background: {accent}; }}
        QPushButton#BtnRed    {{ background: #da3633; color: #fff; border-color: #a0201e; }}
        QPushButton#BtnRed:hover    {{ background: #f85149; }}
        QPushButton#BtnOrange {{ background: {orange}; color: #fff; border-color: {orange_dk}; }}
        QPushButton#BtnOrange:hover {{ background: #e3a020; }}
        QPushButton#BtnTeal   {{ background: #14b8a6; color: #fff; border-color: #0d7a6e; }}
        QPushButton#BtnTeal:hover   {{ background: #2dd4bf; }}
        QPushButton#BtnPurple {{ background: #6e40c9; color: #fff; border-color: #5a32a3; }}
        QPushButton#BtnPurple:hover {{ background: {purple}; }}
        QPushButton#BtnGray   {{ background: {bg3}; color: {text}; border: 1px solid {border}; }}
        QPushButton#BtnGray:hover   {{ background: {border}; }}
        QPushButton#BtnYellow {{ background: #d29922; color: #fff; border-color: #9e6a03; font-weight: 700; }}
        QPushButton#BtnYellow:hover {{ background: #e3a020; }}
        QPushButton#BtnCyan   {{ background: #0e7490; color: #fff; border-color: #0a5970; }}
        QPushButton#BtnCyan:hover   {{ background: #0891b2; }}

        /* Toggle buttons */
        QPushButton#TabToggle {{
            background: {accent2};
            color: #fff;
            border-color: #1158b0;
            font-weight: 700;
        }}
        QPushButton#TabToggle:hover {{ background: {accent}; }}
        QPushButton#TabToggleOff {{
            background: {bg3};
            color: {text_dim};
            border: 1px solid {border};
        }}
        QPushButton#TabToggleOff:hover {{ background: {border}; color: {text}; }}

        /* ── Inputs ── */
        QTextEdit, QLineEdit {{
            background: {bg3};
            border: 1px solid {border};
            border-radius: 5px;
            color: {text};
            padding: 6px 10px;
            font-size: 12px;
        }}
        QTextEdit:focus, QLineEdit:focus {{ border-color: {accent}; background: {bg2}; }}
        QComboBox {{
            background: {bg3};
            border: 1px solid {border};
            border-radius: 5px;
            color: {text};
            padding: 4px 10px;
            min-height: 28px;
        }}
        QComboBox:focus {{ border-color: {accent}; }}
        QComboBox::drop-down {{ border: none; width: 22px; }}
        QComboBox QAbstractItemView {{
            background: {bg2};
            border: 1px solid {border};
            color: {text};
            selection-background-color: {accent2};
        }}

        /* ── ScrollBar ── */
        QScrollBar:vertical {{
            background: transparent; width: 7px; margin: 2px 1px;
        }}
        QScrollBar::handle:vertical {{
            background: {border}; border-radius: 3px; min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{ background: {text_dim}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar:horizontal {{
            background: transparent; height: 7px;
        }}
        QScrollBar::handle:horizontal {{
            background: {border}; border-radius: 3px; min-width: 20px;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

        /* ── Log area ── */
        QTextEdit#LogArea {{
            background: {bg3};
            border: 1px solid {border};
            border-radius: 6px;
            color: {teal};
            font-family: 'Consolas', monospace;
            font-size: 11px;
            padding: 8px;
        }}

        /* ── Ready bar ── */
        QFrame#ReadyBar {{
            background: rgba(63, 185, 80, 0.07);
            border: 1px solid {green_dk};
            border-radius: 6px;
        }}
        QLabel#ReadyLabel {{
            color: {green};
            background: transparent;
            font-weight: 700;
            font-size: 12px;
        }}

        /* ── Splitter ── */
        QSplitter::handle:horizontal {{ width: 1px; background: {border}; }}
        QSplitter::handle:vertical   {{ height: 1px; background: {border}; }}
        """)
