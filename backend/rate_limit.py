"""In-memory per-client rate limiting for chat endpoints."""

from __future__ import annotations

import os
import time
from collections import defaultdict
from threading import Lock


class RateLimiter:
    """Fixed-window request counter keyed by client identifier (e.g. IP)."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max(1, max_requests)
        self.window_seconds = max(1.0, window_seconds)
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str) -> tuple[bool, int | None]:
        """Return (allowed, retry_after_seconds). retry_after is set when denied."""
        now = time.monotonic()
        window_start = now - self.window_seconds

        with self._lock:
            hits = [t for t in self._hits[key] if t > window_start]
            if len(hits) >= self.max_requests:
                retry_after = int(self.window_seconds - (now - hits[0])) + 1
                self._hits[key] = hits
                return False, max(retry_after, 1)

            hits.append(now)
            self._hits[key] = hits
            return True, None


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def chat_rate_limiter() -> RateLimiter:
    max_requests = _int_env("CHAT_RATE_LIMIT_MAX", 15)
    window_seconds = _int_env("CHAT_RATE_LIMIT_WINDOW", 60)
    return RateLimiter(max_requests, float(window_seconds))


def chat_max_question_length() -> int:
    return max(100, _int_env("CHAT_MAX_QUESTION_LENGTH", 2000))
