"""
Async Rate Limiter & Backoff for Reddit API.
"""

import asyncio
import time
import logging

logger = logging.getLogger(__name__)


class AsyncRateLimiter:
    """Fast Token bucket rate limiter."""

    def __init__(self, requests_per_minute: int = 60):
        self.capacity = float(max(requests_per_minute, 30))
        self.tokens = self.capacity
        self.fill_rate = self.capacity / 60.0  # tokens per second
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Acquire a token with minimal async wait."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.last_update = now

            self.tokens = min(self.capacity, self.tokens + elapsed * self.fill_rate)

            if self.tokens < 1.0:
                sleep_time = min((1.0 - self.tokens) / self.fill_rate, 0.5)
                await asyncio.sleep(sleep_time)
                self.last_update = time.monotonic()
                self.tokens = 0.0
            else:
                self.tokens -= 1.0
