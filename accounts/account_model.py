"""
Model dữ liệu cho một tài khoản Grok
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Account:
    email: str
    password: str
    status: str = "pending"          # pending | logged_in | error
    last_login: Optional[str] = None # ISO string "2026-03-11 08:30"
    error_msg: str = ""
    chrome_port: Optional[int] = None
    profile_dir: str = ""            # đường dẫn Chrome profile riêng

    def to_dict(self) -> dict:
        return {
            "email":       self.email,
            "password":    self.password,
            "status":      self.status,
            "last_login":  self.last_login,
            "error_msg":   self.error_msg,
            "chrome_port": self.chrome_port,
            "profile_dir": self.profile_dir,
        }

    @staticmethod
    def from_dict(d: dict) -> "Account":
        return Account(
            email       = d.get("email", ""),
            password    = d.get("password", ""),
            status      = d.get("status", "pending"),
            last_login  = d.get("last_login"),
            error_msg   = d.get("error_msg", ""),
            chrome_port = d.get("chrome_port"),
            profile_dir = d.get("profile_dir", ""),
        )

    @property
    def last_login_short(self) -> str:
        if not self.last_login:
            return "-"
        return self.last_login[:16]   # "2026-03-11 08:30"
