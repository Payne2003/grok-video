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
            border_light = "#3d444d"
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
            shadow    = "0 4px 12px rgba(0, 0, 0, 0.4)"
        else:
            bg        = "#f6f8fa"
            bg2       = "#ffffff"
            bg3       = "#eaeef2"
            border    = "#d0d7de"
            border_light = "#e5e7eb"
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
            shadow    = "0 2px 8px rgba(0, 0, 0, 0.1)"

        self.setStyleSheet(f"""
        /* ── Global ── */
        QMainWindow, QWidget {{
            background: {bg};
            color: {text};
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
            font-size: 13px;
        }}

        /* ── Header ── */
        QFrame#AppHeader {{
            background: {header_bg};
            border-bottom: 1px solid {border};
        }}
        QLabel#AppTitle {{ 
            color: {text}; 
            font-size: 28px;
            font-weight: 700;
            letter-spacing: -0.5px;
        }}
        QLabel#VerLabel  {{ 
            color: {text_dim};
            font-weight: 500;
        }}

        QPushButton#BtnUpdate {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e3a020, stop:1 {orange});
            color: #ffffff;
            border: none;
            border-radius: 6px;
            padding: 0 16px;
            font-weight: 600;
            font-size: 12px;
            transition: all 0.2s ease;
        }}
        QPushButton#BtnUpdate:hover {{ 
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f0a830, stop:1 #e0a020);
        }}
        QPushButton#BtnUpdate:pressed {{ background: #b08020; }}
        
        QPushButton#BtnDark {{
            background: {bg3};
            color: {text};
            border: 1px solid {border};
            border-radius: 6px;
            padding: 0 16px;
            font-size: 12px;
            transition: all 0.2s ease;
        }}
        QPushButton#BtnDark:hover {{ 
            background: {border_light};
            border-color: {accent};
        }}
        QPushButton#BtnDark:pressed {{ background: {border}; }}

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
            transition: all 0.2s ease;
        }}
        QTabWidget#MainTabs QTabBar::tab:selected {{
            background: {accent2};
            color: #ffffff;
            border-radius: 6px 6px 0 0;
            font-weight: 600;
        }}
        QTabWidget#MainTabs QTabBar::tab:hover:!selected {{
            background: {bg3};
            color: {text};
        }}

        /* ── Panels ── */
        QFrame#PanelCard {{
            background: {bg2};
            border: 1px solid {border};
            border-radius: 10px;
        }}
        QLabel#SectionTitle {{
            color: {text};
            font-size: 14px;
            font-weight: 700;
            letter-spacing: -0.3px;
        }}

        /* ── Stat Boxes ── */
        QFrame#StatTotal   {{ 
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {bg2}, stop:1 {bg3});
            border: 2px solid {accent};  
            border-radius: 10px;
            padding: 2px;
        }}
        QFrame#StatRunning {{ 
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {bg2}, stop:1 {bg3});
            border: 2px solid {orange};  
            border-radius: 10px;
            padding: 2px;
        }}
        QFrame#StatDone    {{ 
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {bg2}, stop:1 {bg3});
            border: 2px solid {green};   
            border-radius: 10px;
            padding: 2px;
        }}
        QFrame#StatError   {{ 
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {bg2}, stop:1 {bg3});
            border: 2px solid {red};     
            border-radius: 10px;
            padding: 2px;
        }}

        QLabel#StatNumTotal   {{ color: {accent};  font-size: 36px; font-weight: 800; }}
        QLabel#StatNumRunning {{ color: {orange};  font-size: 36px; font-weight: 800; }}
        QLabel#StatNumDone    {{ color: {green};   font-size: 36px; font-weight: 800; }}
        QLabel#StatNumError   {{ color: {red};     font-size: 36px; font-weight: 800; }}
        QLabel#StatLabel      {{ color: {text_dim}; font-size: 12px; font-weight: 600; }}

        /* ── Table ── */
        QTableWidget {{
            background: {bg2};
            border: 1px solid {border};
            border-radius: 8px;
            gridline-color: {border};
            color: {text};
            selection-background-color: {accent2};
        }}
        QTableWidget::item {{ padding: 6px 8px; }}
        QTableWidget::item:hover {{ background: {bg3}; }}
        QHeaderView::section {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {bg3}, stop:1 {bg2});
            color: {text_dim};
            border: none;
            border-bottom: 1px solid {border};
            padding: 8px;
            font-weight: 600;
            font-size: 12px;
        }}
        QTableWidget::item:selected {{ background: {accent2}; color: #fff; }}

        /* ── Buttons ── */
        QPushButton {{ 
            border-radius: 6px; 
            padding: 6px 14px; 
            font-size: 12px; 
            font-weight: 500; 
            border: none;
            transition: all 0.15s ease;
        }}

        QPushButton#BtnGreen  {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2ea043, stop:1 #238636); color: #fff; }}
        QPushButton#BtnGreen:hover  {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3fb950, stop:1 #2ea043); }}
        QPushButton#BtnGreen:pressed  {{ background: #238636; }}
        
        QPushButton#BtnBlue   {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {accent}, stop:1 {accent2}); color: #fff; }}
        QPushButton#BtnBlue:hover   {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #6db3f2, stop:1 {accent}); }}
        QPushButton#BtnBlue:pressed   {{ background: {accent2}; }}
        
        QPushButton#BtnRed    {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f85149, stop:1 #da3633); color: #fff; }}
        QPushButton#BtnRed:hover    {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #fa7a6d, stop:1 #f85149); }}
        QPushButton#BtnRed:pressed    {{ background: #da3633; }}
        
        QPushButton#BtnOrange {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e3a020, stop:1 {orange}); color: #fff; }}
        QPushButton#BtnOrange:hover {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f0a830, stop:1 #e3a020); }}
        QPushButton#BtnOrange:pressed {{ background: {orange}; }}
        
        QPushButton#BtnTeal   {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #27865e, stop:1 #1f6a5c); color: #fff; }}
        QPushButton#BtnTeal:hover   {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2ba06f, stop:1 #27865e); }}
        QPushButton#BtnTeal:pressed   {{ background: #1f6a5c; }}
        
        QPushButton#BtnPurple {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #8250df, stop:1 #6e40c9); color: #fff; }}
        QPushButton#BtnPurple:hover {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {purple}, stop:1 #8250df); }}
        QPushButton#BtnPurple:pressed {{ background: #6e40c9; }}
        
        QPushButton#BtnGray   {{ background: {bg3}; color: {text}; border: 1px solid {border}; }}
        QPushButton#BtnGray:hover   {{ background: {border_light}; border-color: {accent}; }}
        QPushButton#BtnGray:pressed   {{ background: {border}; }}
        
        QPushButton#BtnCyan   {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0891b2, stop:1 #0e7490); color: #fff; }}
        QPushButton#BtnCyan:hover   {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #06b6d4, stop:1 #0891b2); }}
        QPushButton#BtnCyan:pressed   {{ background: #0e7490; }}

        /* Tab-like toggle buttons */
        QPushButton#TabToggle {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {accent}, stop:1 {accent2});
            color: #fff;
            border-radius: 6px;
            padding: 6px 18px;
            font-weight: 600;
            border: none;
        }}
        QPushButton#TabToggle:hover {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #6db3f2, stop:1 {accent});
        }}
        QPushButton#TabToggleOff {{
            background: {bg3};
            color: {text_dim};
            border-radius: 6px;
            padding: 6px 18px;
            border: 1px solid {border};
            transition: all 0.15s ease;
        }}
        QPushButton#TabToggleOff:hover {{
            background: {border_light};
            color: {text};
            border-color: {accent};
        }}

        /* ── Inputs ── */
        QTextEdit, QLineEdit {{
            background: {bg3};
            border: 1px solid {border};
            border-radius: 6px;
            color: {text};
            padding: 8px 10px;
            font-size: 12px;
            selection-background-color: {accent2};
        }}
        QTextEdit:focus, QLineEdit:focus {{ 
            border: 1px solid {accent}; 
            outline: none;
        }}
        QComboBox {{
            background: {bg3};
            border: 1px solid {border};
            border-radius: 6px;
            color: {text};
            padding: 6px 10px;
            font-size: 12px;
        }}
        QComboBox:focus {{ border-color: {accent}; }}
        QComboBox QAbstractItemView {{ 
            background: {bg2}; 
            color: {text}; 
            border: 1px solid {border};
            selection-background-color: {accent2};
        }}

        /* ── ScrollBar ── */
        QScrollBar:vertical {{
            background: {bg}; 
            width: 10px; 
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {border}; 
            border-radius: 5px; 
            min-height: 24px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {border_light};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

        /* ── Status badge ── */
        QLabel#BadgeGreen  {{ 
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3fb950, stop:1 #238636); 
            color: #fff; 
            border-radius: 5px; 
            padding: 3px 10px; 
            font-size: 11px; 
            font-weight: 600; 
        }}
        QLabel#BadgeOrange {{ 
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {orange}, stop:1 #b08020); 
            color: #fff; 
            border-radius: 5px; 
            padding: 3px 10px; 
            font-size: 11px; 
            font-weight: 600; 
        }}
        QLabel#BadgeRed    {{ 
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f85149, stop:1 #da3633); 
            color: #fff; 
            border-radius: 5px; 
            padding: 3px 10px; 
            font-size: 11px; 
            font-weight: 600; 
        }}

        /* ── Log area ── */
        QTextEdit#LogArea {{
            background: {bg3};
            border: 1px solid {border};
            border-radius: 8px;
            color: {teal};
            font-family: 'Cascadia Code', 'Consolas', monospace;
            font-size: 11px;
            padding: 8px;
        }}

        /* ── Ready bar ── */
        QFrame#ReadyBar {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {bg2}, stop:1 {bg3});
            border: 1px solid {green};
            border-radius: 8px;
        }}
        QLabel#ReadyLabel {{ 
            color: {green}; 
            font-weight: 600;
            font-size: 12px;
        }}

        /* ── Splitter ── */
        QSplitter::handle {{ 
            background: {border}; 
            width: 1px;
        }}

        QLabel {{ color: {text}; }}
        """)
