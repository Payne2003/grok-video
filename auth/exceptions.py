"""auth/exceptions.py — Custom exceptions for the auth module."""

class AuthError(Exception):
    """Base exception for all auth errors."""

class SessionCorruptedError(AuthError):
    """Raised when session file exists but data is invalid or unreadable."""

class SessionSaveError(AuthError):
    """Raised when cookies cannot be persisted to disk."""

class LoginTimeoutError(AuthError):
    """Raised when manual login exceeds the allowed timeout window."""

class BrowserNotReadyError(AuthError):
    """Raised when browser / page is not initialised yet."""