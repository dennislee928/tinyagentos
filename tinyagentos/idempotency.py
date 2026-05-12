"""Idempotency-Key support for POST endpoints that create durable resources.

If a request carries an `Idempotency-Key` header, the (key, endpoint, user_id)
tuple is cached for 24h. A repeat request with the same key and endpoint
returns the cached response — useful when an agent retries a deploy after a
network blip and shouldn't end up with two agents.

The cache lives on `app.state.idempotency_cache` so each app instance gets
its own (tests are isolated; production gets one shared cache per worker).
In-memory only; persistence across restarts is a Pass 2+ concern.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

_TTL_SECONDS = 24 * 3600


class IdempotencyCache:
    def __init__(self) -> None:
        self._entries: dict[tuple[str, str, str], tuple[Any, float]] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, key: str, endpoint: str, user_id: str) -> Any | None:
        async with self._lock:
            entry = self._entries.get((key, endpoint, user_id))
            if entry is None:
                return None
            value, ts = entry
            if time.time() - ts > _TTL_SECONDS:
                self._entries.pop((key, endpoint, user_id), None)
                return None
            return value

    async def set(self, *, key: str, endpoint: str, user_id: str, value: Any) -> None:
        async with self._lock:
            self._entries[(key, endpoint, user_id)] = (value, time.time())
