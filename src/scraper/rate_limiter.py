from __future__ import annotations

import asyncio
import time

from src.config import settings


class RateLimiter:
    """Enforces a minimum delay between page requests to avoid being banned."""

    def __init__(self, delay_seconds: int | None = None):
        self._delay = delay_seconds or settings.scrape_delay_seconds
        self._lock = asyncio.Lock()
        self._last_request_time: float = 0

    async def wait(self):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self._delay:
                await asyncio.sleep(self._delay - elapsed)
            self._last_request_time = time.monotonic()
