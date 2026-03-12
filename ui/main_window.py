from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout
from ui.log_panel import LogPanel
from ui.login_panel import LoginPanel

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Grok Video Tool")

        central = QWidget()

        layout = QVBoxLayout()

        self.log_panel = LogPanel()

        self.login_panel = LoginPanel(self.write_log)

        layout.addWidget(self.login_panel)
        layout.addWidget(self.log_panel)

        central.setLayout(layout)

        self.setCentralWidget(central)

    def write_log(self, message):

        self.log_panel.write_log(message)
