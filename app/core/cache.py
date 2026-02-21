"""
L1/L2 two-level cache.

L1: In-process TTLCache  — ~50ns,  no network
L2: Redis async          — ~0.3ms, survives restarts

Write path: L1 sync write → L2 fire-and-forget (non-blocking response).
Read path: L1 check → L2 check → None (compute needed).
"""
import asyncio
import hashlib
import json
import logging
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ── L1: Bounded in-process TTL cache ─────────────────────────────────────────
try:
    from cachetools import TTLCache
    _l1: TTLCache = TTLCache(maxsize=settings.l1_cache_maxsize, ttl=settings.cache_ttl_seconds)
    _L1_OK = True
except ImportError:
    _l1 = {}          # type: ignore
    _L1_OK = False

# ── L2: Redis async ───────────────────────────────────────────────────────────
try:
    import redis.asyncio as aioredis
    _REDIS_OK = True
except ImportError:
    _REDIS_OK = False

_pool: Optional[object] = None
_redis: Optional[object] = None


async def _get_redis():
    global _pool, _redis
    if not _REDIS_OK:
        return None
    if _redis is None:
        try:
            _pool = aioredis.ConnectionPool.from_url(
                settings.redis_url,
                max_connections=settings.redis_pool_size,
                socket_connect_timeout=1,
                socket_timeout=0.5,
                decode_responses=True,
            )
            _redis = aioredis.Redis(connection_pool=_pool)
        except Exception as e:
            logger.warning("Redis unavailable", extra={"error": str(e)})
            return None
    return _redis


def make_cache_key(method: str, path: str, body: bytes) -> str:
    """Canonical cache key: SHA-256(method:path:sorted-JSON-body)."""
    try:
        canonical = json.dumps(json.loads(body), sort_keys=True, separators=(",", ":"))
    except Exception:
        canonical = body.decode("utf-8", errors="replace")
    return "c:" + hashlib.sha256(f"{method}:{path}:{canonical}".encode()).hexdigest()[:32]


async def cache_get(key: str) -> Optional[str]:
    """L1 hit (~50ns) → L2 hit (~0.3ms) → None."""
    if _L1_OK:
        val = _l1.get(key)
        if val is not None:
            return val

    r = await _get_redis()
    if r is None:
        return None
    try:
        val = await r.get(key)
        if val is not None and _L1_OK:
            _l1[key] = val          # promote to L1
        return val
    except Exception as e:
        logger.debug("Redis GET error", extra={"error": str(e)})
        return None


async def cache_set(key: str, value: str) -> None:
    """Write to L1 immediately; write to Redis as background task (non-blocking)."""
    if _L1_OK:
        _l1[key] = value

    r = await _get_redis()
    if r is None:
        return

    async def _write():
        try:
            await r.setex(key, settings.cache_ttl_seconds, value)
        except Exception as e:
            logger.debug("Redis SET error", extra={"error": str(e)})

    # asyncio.create_task — schedules on running loop without blocking caller
    try:
        asyncio.get_running_loop().create_task(_write())
    except RuntimeError:
        pass    # no running loop in tests — silently skip
