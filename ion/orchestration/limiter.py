from __future__ import annotations

import asyncio
import time
from collections import deque


class SlidingWindowRateLimiter:
    """One shared, process-wide sliding-window limiter for NVIDIA API calls."""

    def __init__(self, limit: int = 40, window_seconds: float = 60.0) -> None:
        self.limit = max(1, limit)
        self.window = max(1.0, window_seconds)
        self._events: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                cutoff = now - self.window
                while self._events and self._events[0] <= cutoff:
                    self._events.popleft()
                if len(self._events) < self.limit:
                    self._events.append(now)
                    return
                delay = max(0.01, self._events[0] + self.window - now)
                await asyncio.sleep(delay)

    @property
    def recent_count(self) -> int:
        cutoff = time.monotonic() - self.window
        return sum(1 for item in self._events if item > cutoff)
