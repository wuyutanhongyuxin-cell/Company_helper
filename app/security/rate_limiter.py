"""
Rate Limiter Module - 登录速率限制模块
Provides login attempt rate limiting to prevent brute force attacks.
"""

import time
from typing import Dict, Tuple, Optional
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class AttemptRecord:
    """Record of login attempts for a user/IP."""
    attempts: int = 0
    first_attempt_time: float = 0.0
    locked_until: float = 0.0


class RateLimiter:
    """
    Rate limiter for login attempts.
    速率限制器 - 防止暴力破解攻击
    
    Default settings:
    - 5 failed attempts within 5 minutes triggers a lockout
    - Lockout duration is 5 minutes
    """
    
    def __init__(
        self,
        max_attempts: int = 5,
        window_seconds: int = 300,
        lockout_seconds: int = 300,
    ):
        """
        Initialize rate limiter.
        
        Args:
            max_attempts: Maximum failed attempts before lockout
            window_seconds: Time window for counting attempts (seconds)
            lockout_seconds: Duration of lockout (seconds)
        """
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        
        self._records: Dict[str, AttemptRecord] = {}
        self._lock = Lock()
    
    def _get_record(self, identifier: str) -> AttemptRecord:
        """Get or create attempt record for an identifier."""
        if identifier not in self._records:
            self._records[identifier] = AttemptRecord()
        return self._records[identifier]
    
    def _cleanup_expired(self, record: AttemptRecord, now: float) -> None:
        """Reset record if window has expired."""
        if record.first_attempt_time > 0:
            if now - record.first_attempt_time > self.window_seconds:
                record.attempts = 0
                record.first_attempt_time = 0.0
    
    def is_locked(self, identifier: str) -> Tuple[bool, int]:
        """
        Check if an identifier is currently locked out.
        
        Args:
            identifier: User ID or IP address
            
        Returns:
            Tuple of (is_locked, remaining_seconds)
        """
        with self._lock:
            now = time.time()
            record = self._get_record(identifier)
            
            if record.locked_until > now:
                remaining = int(record.locked_until - now)
                return True, remaining
            
            return False, 0
    
    def get_remaining_attempts(self, identifier: str) -> int:
        """
        Get the number of remaining login attempts.
        
        Args:
            identifier: User ID or IP address
            
        Returns:
            Number of remaining attempts before lockout
        """
        with self._lock:
            now = time.time()
            record = self._get_record(identifier)
            
            self._cleanup_expired(record, now)
            
            return max(0, self.max_attempts - record.attempts)
    
    def record_attempt(self, identifier: str, success: bool) -> None:
        """
        Record a login attempt.
        
        Args:
            identifier: User ID or IP address
            success: Whether the login was successful
        """
        with self._lock:
            now = time.time()
            record = self._get_record(identifier)
            
            if success:
                # Reset on successful login
                record.attempts = 0
                record.first_attempt_time = 0.0
                record.locked_until = 0.0
                return
            
            # Failed attempt
            self._cleanup_expired(record, now)
            
            if record.attempts == 0:
                record.first_attempt_time = now
            
            record.attempts += 1
            
            # Lock if max attempts reached
            if record.attempts >= self.max_attempts:
                record.locked_until = now + self.lockout_seconds
    
    def unlock(self, identifier: str) -> None:
        """
        Manually unlock an identifier.
        
        Args:
            identifier: User ID or IP address
        """
        with self._lock:
            if identifier in self._records:
                record = self._records[identifier]
                record.attempts = 0
                record.first_attempt_time = 0.0
                record.locked_until = 0.0
    
    def clear_all(self) -> None:
        """Clear all records (for testing purposes)."""
        with self._lock:
            self._records.clear()


# Singleton instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """
    Get or create the singleton RateLimiter instance.
    
    Returns:
        RateLimiter instance
    """
    global _rate_limiter
    
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    
    return _rate_limiter


def reset_rate_limiter() -> None:
    """Reset the singleton instance (for testing purposes)."""
    global _rate_limiter
    _rate_limiter = None
