"""
controllers/generator_controller.py
"""

from PySide6.QtWidgets import QFileDialog
from pathlib import Path


class GeneratorController:

    MODE_TEXT  = "text"
    MODE_IMAGE = "image"

    def __init__(self, panel):

        self.ui = panel
        self.mode = self.MODE_TEXT

        self.default_output = Path("D:/grok-video-tool/outputs")

        self._connect()
        self._init_state()

    # ──────────────────────────────────────────
    # INIT
    # ──────────────────────────────────────────

    def _init_state(self):

        if not self.default_output.exists():
            self.default_output.mkdir(parents=True, exist_ok=True)

        self.ui.out_path.setText(str(self.default_output))

        self._apply_mode()

    # ──────────────────────────────────────────
    # SIGNAL CONNECT
    # ──────────────────────────────────────────

    def _connect(self):

        self.ui.btn_text.clicked.connect(self.set_text_mode)
        self.ui.btn_image.clicked.connect(self.set_image_mode)

        # output folder button (...)
        self.ui.out_path.parent().findChild(type(self.ui.btn_text), "...")

        # tìm button browse
        for w in self.ui.findChildren(type(self.ui.btn_text)):
            if w.text() == "...":
                w.clicked.connect(self.choose_output)

        # import folder button
        for w in self.ui.findChildren(type(self.ui.btn_text)):
            if "Nhập Folder" in w.text():
                w.clicked.connect(self.import_folder)

    # ──────────────────────────────────────────
    # MODE SWITCH
    # ──────────────────────────────────────────

    def set_text_mode(self):

        if self.mode == self.MODE_TEXT:
            return

        self.mode = self.MODE_TEXT
        self._apply_mode()

    def set_image_mode(self):

        if self.mode == self.MODE_IMAGE:
            return

        self.mode = self.MODE_IMAGE
        self._apply_mode()

    # ──────────────────────────────────────────

    def _apply_mode(self):

        if self.mode == self.MODE_TEXT:

            self.ui.btn_text.setObjectName("TabToggle")
            self.ui.btn_image.setObjectName("TabToggleOff")

            self.ui.prompt.setEnabled(True)

        else:

            self.ui.btn_text.setObjectName("TabToggleOff")
            self.ui.btn_image.setObjectName("TabToggle")

            # image mode không nhập prompt
            self.ui.prompt.setEnabled(False)

        self.ui.btn_text.style().unpolish(self.ui.btn_text)
        self.ui.btn_text.style().polish(self.ui.btn_text)

        self.ui.btn_image.style().unpolish(self.ui.btn_image)
        self.ui.btn_image.style().polish(self.ui.btn_image)

    # ──────────────────────────────────────────
    # OUTPUT FOLDER
    # ──────────────────────────────────────────

    def choose_output(self):

        folder = QFileDialog.getExistingDirectory(
            None,
            "Chọn thư mục output",
            self.ui.out_path.text()
        )

        if folder:
            self.ui.out_path.setText(folder)

    def get_output_path(self):

        return Path(self.ui.out_path.text())

    # ──────────────────────────────────────────
    # IMPORT IMAGE FOLDER
    # ──────────────────────────────────────────

    def import_folder(self):

        if self.mode != self.MODE_IMAGE:
            return

        folder = QFileDialog.getExistingDirectory(
            None,
            "Chọn thư mục ảnh"
        )

        if not folder:
            return

        path = Path(folder)

        images = list(path.glob("*.png"))
        images += list(path.glob("*.jpg"))
        images += list(path.glob("*.jpeg"))

        self._load_images(images)

    # ──────────────────────────────────────────
    # LOAD QUEUE
    # ──────────────────────────────────────────

    def _load_images(self, images):

        table = self.ui.table

        table.setRowCount(0)

        for i, img in enumerate(images):

            row = table.rowCount()
            table.insertRow(row)

            table.setItem(row, 0, self._item(str(i + 1)))
            table.setItem(row, 1, self._item(img.name))
            table.setItem(row, 2, self._item("Chờ"))

    # ──────────────────────────────────────────

    def _item(self, text):

        from PySide6.QtWidgets import QTableWidgetItem
        return QTableWidgetItem(text)
