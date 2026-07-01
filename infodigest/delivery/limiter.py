"""Token bucket rate limiter for delivery channels."""

from __future__ import annotations

import time
import threading


class TokenBucketLimiter:
    """Simple token bucket rate limiter.

    Args:
        rate: Tokens per second (e.g. 5/60 for 5/min).
        max_tokens: Maximum burst capacity.
    """

    def __init__(self, rate: float, max_tokens: int = 1) -> None:
        self._rate = rate
        self._max_tokens = max_tokens
        self._tokens = float(max_tokens)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._max_tokens, self._tokens + elapsed * self._rate)
        self._last_refill = now

    def acquire(self, timeout: float = 60.0) -> bool:
        """Acquire a token, blocking until available or timeout.

        Returns True if acquired, False if timed out.
        """
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return True

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False

            # Sleep briefly then retry
            time.sleep(min(0.1, remaining))

    def try_acquire(self) -> bool:
        """Try to acquire a token without blocking.

        Returns True if acquired immediately, False otherwise.
        """
        with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False


# Pre-built limiters for known channels
def feishu_limiter() -> TokenBucketLimiter:
    """Feishu: 5 messages per minute."""
    return TokenBucketLimiter(rate=5.0 / 60.0, max_tokens=5)


def dingtalk_limiter() -> TokenBucketLimiter:
    """DingTalk: 20 messages per minute."""
    return TokenBucketLimiter(rate=20.0 / 60.0, max_tokens=20)
