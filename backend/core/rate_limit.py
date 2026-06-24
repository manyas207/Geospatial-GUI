"""In-memory per-client rate limiting for chat endpoints."""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

from backend.core.limits import chat_rate_limit_max, chat_rate_limit_window


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


def chat_rate_limiter() -> RateLimiter:
    return RateLimiter(chat_rate_limit_max(), float(chat_rate_limit_window()))
