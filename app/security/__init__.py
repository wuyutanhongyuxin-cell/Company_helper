"""
Security module - 安全模块
Provides encryption, password hashing, rate limiting, and data sanitization.
"""

from .core import (
    EncryptionManager,
    PasswordManager,
    get_encryption_manager,
    get_password_manager,
)
from .rate_limiter import (
    RateLimiter,
    get_rate_limiter,
)
from .sanitizer import (
    sanitize_for_spreadsheet,
    sanitize_dataframe_for_export,
)

__all__ = [
    # Core
    "EncryptionManager",
    "PasswordManager",
    "get_encryption_manager",
    "get_password_manager",
    # Rate Limiter
    "RateLimiter",
    "get_rate_limiter",
    # Sanitizer
    "sanitize_for_spreadsheet",
    "sanitize_dataframe_for_export",
]
