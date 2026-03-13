from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTabWidget, QLabel, QFrame
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QIcon

from ui.login_panel import LoginPanel
from ui.generator_panel import GeneratorPanel
from ui.image_panel import ImagePanel
from ui.extend_panel import ExtendPanel
from ui.history_panel import HistoryPanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎬 Grok Video Generator")
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
        header.setFixedHeight(60)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(18, 0, 18, 0)

        icon_lbl = QLabel("🎬")
        icon_lbl.setFont(QFont("Segoe UI Emoji", 20))
        title_lbl = QLabel("Grok Video Generator")
        title_lbl.setObjectName("AppTitle")
        title_lbl.setFont(QFont("Segoe UI", 30, QFont.Bold))
        ver_lbl = QLabel("v2.2.0")
        ver_lbl.setObjectName("VerLabel")
        ver_lbl.setFont(QFont("Segoe UI", 9))

        h_layout.addWidget(icon_lbl)
        h_layout.addSpacing(8)
        h_layout.addWidget(title_lbl)
        h_layout.addSpacing(8)
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

        self.login_panel = LoginPanel()
        self.generator_panel = GeneratorPanel()
        self.image_panel = ImagePanel()
        self.extend_panel = ExtendPanel()
        self.history_panel = HistoryPanel()

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
            bg        = "#0d1117"
            bg2       = "#161b22"
            bg3       = "#21262d"
            border    = "#30363d"
            text      = "#e6edf3"
            text_dim  = "#8b949e"
            accent    = "#58a6ff"
            accent2   = "#1f6feb"
            green     = "#3fb950"
            orange    = "#d29922"
            red       = "#f85149"
            purple    = "#bc8cff"
            teal      = "#39d353"
            header_bg = "#010409"
        else:
            bg        = "#f6f8fa"
            bg2       = "#ffffff"
            bg3       = "#eaeef2"
            border    = "#d0d7de"
            text      = "#1f2328"
            text_dim  = "#656d76"
            accent    = "#0969da"
            accent2   = "#0550ae"
            green     = "#1a7f37"
            orange    = "#9a6700"
            red       = "#cf222e"
            purple    = "#8250df"
            teal      = "#1a7f37"
            header_bg = "#24292f"

        self.setStyleSheet(f"""
        /* ── Global ── */
        QMainWindow, QWidget {{
            background: {bg};
            color: {text};
            font-family: 'Segoe UI', sans-serif;
            font-size: 13px;
        }}

        /* ── Header ── */
        QFrame#AppHeader {{
            background: {header_bg};
            border-bottom: 1px solid {border};
        }}
        QLabel#AppTitle {{ color: {text}; }}
        QLabel#VerLabel  {{ color: {text_dim}; }}

        QPushButton#BtnUpdate {{
            background: {orange};
            color: #ffffff;
            border: none;
            border-radius: 6px;
            padding: 0 16px;
            font-weight: 600;
            font-size: 12px;
        }}
        QPushButton#BtnUpdate:hover {{ background: #b08020; }}
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
        QTabWidget#MainTabs QTabBar::tab {{
            background: {bg2};
            color: {text_dim};
            border: none;
            padding: 10px 22px;
            font-size: 13px;
            font-weight: 500;
            margin-right: 2px;
        }}
        QTabWidget#MainTabs QTabBar::tab:selected {{
            background: {accent2};
            color: #ffffff;
            border-radius: 0;
        }}
        QTabWidget#MainTabs QTabBar::tab:hover:!selected {{
            background: {bg3};
            color: {text};
        }}

        /* ── Panels ── */
        QFrame#PanelCard {{
            background: {bg2};
            border: 1px solid {border};
            border-radius: 8px;
        }}
        QLabel#SectionTitle {{
            color: {text};
            font-size: 14px;
            font-weight: 600;
        }}

        /* ── Stat Boxes ── */
        QFrame#StatTotal   {{ background: {bg2}; border: 2px solid {accent};  border-radius: 8px; }}
        QFrame#StatRunning {{ background: {bg2}; border: 2px solid {orange};  border-radius: 8px; }}
        QFrame#StatDone    {{ background: {bg2}; border: 2px solid {green};   border-radius: 8px; }}
        QFrame#StatError   {{ background: {bg2}; border: 2px solid {red};     border-radius: 8px; }}

        QLabel#StatNumTotal   {{ color: {accent};  font-size: 36px; font-weight: 700; }}
        QLabel#StatNumRunning {{ color: {orange};  font-size: 36px; font-weight: 700; }}
        QLabel#StatNumDone    {{ color: {green};   font-size: 36px; font-weight: 700; }}
        QLabel#StatNumError   {{ color: {red};     font-size: 36px; font-weight: 700; }}
        QLabel#StatLabel      {{ color: {text_dim}; font-size: 12px; }}

        /* ── Table ── */
        QTableWidget {{
            background: {bg2};
            border: 1px solid {border};
            border-radius: 6px;
            gridline-color: {border};
            color: {text};
            selection-background-color: {accent2};
        }}
        QTableWidget::item {{ padding: 4px 8px; }}
        QHeaderView::section {{
            background: {bg3};
            color: {text_dim};
            border: none;
            border-bottom: 1px solid {border};
            padding: 6px 8px;
            font-weight: 600;
            font-size: 12px;
        }}
        QTableWidget::item:selected {{ background: {accent2}; color: #fff; }}

        /* ── Buttons ── */
        QPushButton {{ border-radius: 5px; padding: 6px 14px; font-size: 12px; font-weight: 500; border: none; }}

        QPushButton#BtnGreen  {{ background: #238636; color: #fff; }}
        QPushButton#BtnGreen:hover  {{ background: #2ea043; }}
        QPushButton#BtnBlue   {{ background: {accent2}; color: #fff; }}
        QPushButton#BtnBlue:hover   {{ background: {accent}; }}
        QPushButton#BtnRed    {{ background: #da3633; color: #fff; }}
        QPushButton#BtnRed:hover    {{ background: #f85149; }}
        QPushButton#BtnOrange {{ background: {orange}; color: #fff; }}
        QPushButton#BtnOrange:hover {{ background: #e3a020; }}
        QPushButton#BtnTeal   {{ background: #1f6a5c; color: #fff; }}
        QPushButton#BtnTeal:hover   {{ background: #27865e; }}
        QPushButton#BtnPurple {{ background: #6e40c9; color: #fff; }}
        QPushButton#BtnPurple:hover {{ background: {purple}; }}
        QPushButton#BtnGray   {{ background: {bg3}; color: {text}; border: 1px solid {border}; }}
        QPushButton#BtnGray:hover   {{ background: {border}; }}
        QPushButton#BtnCyan   {{ background: #0e7490; color: #fff; }}
        QPushButton#BtnCyan:hover   {{ background: #0891b2; }}

        /* Tab-like toggle buttons */
        QPushButton#TabToggle {{
            background: {accent2};
            color: #fff;
            border-radius: 5px;
            padding: 6px 18px;
            font-weight: 600;
        }}
        QPushButton#TabToggleOff {{
            background: {bg3};
            color: {text_dim};
            border-radius: 5px;
            padding: 6px 18px;
        }}

        /* ── Inputs ── */
        QTextEdit, QLineEdit {{
            background: {bg3};
            border: 1px solid {border};
            border-radius: 5px;
            color: {text};
            padding: 6px 10px;
            font-size: 12px;
        }}
        QTextEdit:focus, QLineEdit:focus {{ border-color: {accent}; }}
        QComboBox {{
            background: {bg3};
            border: 1px solid {border};
            border-radius: 5px;
            color: {text};
            padding: 4px 10px;
        }}
        QComboBox QAbstractItemView {{ background: {bg3}; color: {text}; border: 1px solid {border}; }}

        /* ── ScrollBar ── */
        QScrollBar:vertical {{
            background: {bg2}; width: 8px; margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {border}; border-radius: 4px; min-height: 20px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

        /* ── Status badge ── */
        QLabel#BadgeGreen  {{ background: #238636; color: #fff; border-radius: 4px; padding: 2px 10px; font-size: 11px; font-weight: 600; }}
        QLabel#BadgeOrange {{ background: {orange}; color: #fff; border-radius: 4px; padding: 2px 10px; font-size: 11px; font-weight: 600; }}
        QLabel#BadgeRed    {{ background: #da3633; color: #fff; border-radius: 4px; padding: 2px 10px; font-size: 11px; font-weight: 600; }}

        /* ── Log area ── */
        QTextEdit#LogArea {{
            background: {bg3};
            border: 1px solid {border};
            border-radius: 6px;
            color: {teal};
            font-family: 'Consolas', monospace;
            font-size: 11px;
        }}

        /* ── Ready bar ── */
        QFrame#ReadyBar {{
            background: {bg2};
            border: 1px solid {green};
            border-radius: 5px;
        }}
        QLabel#ReadyLabel {{ color: {green}; font-weight: 600; }}

        /* ── Splitter ── */
        QSplitter::handle {{ background: {border}; width: 1px; }}

        QLabel {{ color: {text}; }}
        """)
