"""Application rate limiter.

Built directly on the ``limits`` library with in-memory storage — correct and
free for a single instance (this app targets ~200 users / very low traffic on a
free-tier host). If the app is ever scaled to multiple replicas, swap
``MemoryStorage`` for a shared backend (``limits`` ships Redis/Memcached storage)
so counters are consistent across processes.

We intentionally do not use ``slowapi`` here: its global middleware resolves the
route handler by walking ``app.routes``, which breaks under the current
FastAPI/Starlette that nest included routers in a single mount. Using ``limits``
directly keeps rate limiting under our control and dependency-light.
"""

from __future__ import annotations

from dataclasses import dataclass

from limits import RateLimitItem, parse
from limits.aio.storage import MemoryStorage
from limits.aio.strategies import FixedWindowRateLimiter

from app.core.config import settings

_storage = MemoryStorage()
_strategy = FixedWindowRateLimiter(_storage)

# Parsed once (e.g. "100/minute"). Raises at import if the string is malformed.
default_limit: RateLimitItem = parse(settings.RATE_LIMIT_DEFAULT)


@dataclass(slots=True)
class RateLimitResult:
    allowed: bool
    limit: RateLimitItem
    remaining: int
    reset_at: float


async def check(key: str, limit: RateLimitItem | None = None) -> RateLimitResult:
    """Record a hit for ``key`` and report whether it is within the limit."""
    item = limit or default_limit
    allowed = await _strategy.hit(item, key)
    stats = await _strategy.get_window_stats(item, key)
    return RateLimitResult(
        allowed=allowed,
        limit=item,
        remaining=stats.remaining,
        reset_at=stats.reset_time,
    )
