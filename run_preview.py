import sys
import os
import importlib
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

import ui.main_window as main_window

last_mtime = 0
window = None


def reload_ui():
    global last_mtime, window, main_window

    path = main_window.__file__
    mtime = os.path.getmtime(path)

    if mtime != last_mtime:
        last_mtime = mtime

        print("🔄 Reload UI")

        importlib.reload(main_window)

        if window:
            window.close()

        window = main_window.MainWindow()
        window.show()


app = QApplication(sys.argv)

window = main_window.MainWindow()
window.show()

last_mtime = os.path.getmtime(main_window.__file__)

timer = QTimer()
timer.timeout.connect(reload_ui)
timer.start(1000)

sys.exit(app.exec())
