from PySide6.QtWidgets import QTextEdit

class LogPanel(QTextEdit):

    def __init__(self):
        super().__init__()

        self.setReadOnly(True)

    def write_log(self, message):

        self.append(message)
