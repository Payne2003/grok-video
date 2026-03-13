"""
ui/account_dialog.py

Dialog dùng chung cho Add và Edit account.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QFrame, QSpacerItem,
    QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class AccountDialog(QDialog):
    """
    Mở bằng:
        dlg = AccountDialog(parent, mode="add")          # Thêm mới
        dlg = AccountDialog(parent, mode="edit",         # Sửa
                            email="x@x.com", password="abc123", slot="account_01")

    Sau exec() == Accepted đọc:
        dlg.out_email     → str
        dlg.out_password  → str
    """

    def __init__(self, parent=None, *,
                 mode: str = "add",
                 email: str = "",
                 password: str = "",
                 slot: str = ""):
        super().__init__(parent)
        assert mode in ("add", "edit")
        self._mode   = mode
        self._slot   = slot
        self.out_email    = ""
        self.out_password = ""

        self.setModal(True)
        self.setFixedWidth(430)
        self.setWindowTitle(
            f"✏️  Sửa tài khoản — {slot}" if mode == "edit"
            else "➕  Thêm tài khoản mới"
        )
        self._build(email, password)

    # ─────────────────────────── UI ──────────────────────────────
    def _build(self, email: str, password: str):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)


        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("Divider")
        root.addWidget(sep)

        # ── Form ──────────────────────────────────────────────────
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        # Email
        self.inp_email = QLineEdit(email)
        self.inp_email.setPlaceholderText("example@gmail.com")
        self.inp_email.setFixedHeight(36)
        if self._mode == "edit":
            self.inp_email.setReadOnly(True)
            self.inp_email.setToolTip("Không thể đổi email — hãy xóa và thêm mới")

        # Password + eye toggle
        self.inp_pwd = QLineEdit(password)
        self.inp_pwd.setPlaceholderText("Mật khẩu tài khoản")
        self.inp_pwd.setFixedHeight(36)
        self.inp_pwd.setEchoMode(QLineEdit.Password)

        self.btn_eye = QPushButton("👁")
        self.btn_eye.setFixedSize(36, 36)
        self.btn_eye.setObjectName("BtnGray")
        self.btn_eye.setCheckable(True)
        self.btn_eye.setToolTip("Hiện / ẩn mật khẩu")
        self.btn_eye.toggled.connect(
            lambda on: self.inp_pwd.setEchoMode(
                QLineEdit.Normal if on else QLineEdit.Password))

        pwd_row = QHBoxLayout()
        pwd_row.setSpacing(6)
        pwd_row.addWidget(self.inp_pwd)
        pwd_row.addWidget(self.btn_eye)

        lbl_email = QLabel("Email:")
        lbl_email.setFont(QFont("Segoe UI", 10))
        lbl_pwd   = QLabel("Mật khẩu:")
        lbl_pwd.setFont(QFont("Segoe UI", 10))

        form.addRow(lbl_email, self.inp_email)
        form.addRow(lbl_pwd,   pwd_row)
        root.addLayout(form)

        # ── Hint (edit mode) ──────────────────────────────────────
        if self._mode == "edit":
            hint = QLabel("💡 Email không thể đổi. Chỉ cập nhật mật khẩu.")
            hint.setFont(QFont("Segoe UI", 9))
            hint.setStyleSheet("color: #8b949e; padding: 2px 0;")
            root.addWidget(hint)

        root.addSpacerItem(QSpacerItem(0, 4, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # ── Buttons ───────────────────────────────────────────────
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setObjectName("Divider")
        root.addWidget(sep2)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("  Hủy")
        btn_cancel.setObjectName("BtnGray")
        btn_cancel.setFixedHeight(36)
        btn_cancel.setMinimumWidth(90)
        btn_cancel.clicked.connect(self.reject)

        lbl_ok = "💾  Lưu thay đổi" if self._mode == "edit" else "➕  Thêm tài khoản"
        btn_ok = QPushButton(lbl_ok)
        btn_ok.setObjectName("BtnGreen")
        btn_ok.setFixedHeight(36)
        btn_ok.setMinimumWidth(150)
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._submit)

        btn_row.addWidget(btn_cancel)
        btn_row.addSpacing(8)
        btn_row.addWidget(btn_ok)
        root.addLayout(btn_row)

    # ─────────────────────────── VALIDATE ────────────────────────
    def _submit(self):
        email = self.inp_email.text().strip()
        pwd   = self.inp_pwd.text().strip()

        if self._mode == "add":
            if not email:
                self._shake(self.inp_email, "Email không được để trống!")
                return
            if "@" not in email or "." not in email.split("@")[-1]:
                self._shake(self.inp_email, "Email không hợp lệ!")
                return

        self.out_email    = email
        self.out_password = pwd
        self.accept()

    def _shake(self, widget: QLineEdit, msg: str):
        """Highlight input lỗi."""
        widget.setStyleSheet("border: 1.5px solid #f85149; border-radius: 6px;")
        widget.setFocus()
        widget.setToolTip(msg)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1800, lambda: (
            widget.setStyleSheet(""),
            widget.setToolTip("")
        ))