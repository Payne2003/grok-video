import sys
import os
import importlib

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

import ui.main_window as main_window


window = None
last_mtime = 0


def reload_ui():

    global last_mtime, window, main_window

    path = main_window.__file__.replace(".pyc", ".py")

    mtime = os.path.getmtime(path)

    if mtime == last_mtime:
        return

    last_mtime = mtime

    print("🔄 Reload UI")

    try:

        importlib.reload(main_window)

        if window:
            window.close()
            window.deleteLater()

        window = main_window.MainWindow()
        window.show()

    except Exception as e:

        print("❌ Reload error:", e)


app = QApplication(sys.argv)

window = main_window.MainWindow()
window.show()

last_mtime = os.path.getmtime(main_window.__file__.replace(".pyc",".py"))

timer = QTimer()
timer.timeout.connect(reload_ui)
timer.start(1000)

sys.exit(app.exec())
