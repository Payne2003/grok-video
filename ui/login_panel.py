from PySide6.QtWidgets import QWidget, QPushButton, QVBoxLayout
from auth.login_service import LoginService

class LoginPanel(QWidget):

    def __init__(self, log_callback):
        super().__init__()

        self.log_callback = log_callback

        self.login_service = LoginService(self.log_callback)

        layout = QVBoxLayout()

        self.login_btn = QPushButton("Login Grok")

        self.login_btn.clicked.connect(self.handle_login)

        layout.addWidget(self.login_btn)

        self.setLayout(layout)

    def handle_login(self):

        self.login_service.login()
