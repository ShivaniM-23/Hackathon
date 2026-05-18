"""
ShadowTrace AI — cache.py
Redis-backed caching layer for investigation results.
Falls back to an in-process dict if Redis is unavailable (local dev).
"""

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", str(60 * 60 * 24 * 7)))  # 7 days

# ── Internal state ────────────────────────────────────────────────────────────
_redis = None                        # async Redis client (None if unavailable)
_local_cache: dict[str, str] = {}   # in-process fallback


# ── Lifecycle ─────────────────────────────────────────────────────────────────

async def init_cache() -> None:
    """Connect to Redis. Silently falls back to in-process cache on failure."""
    global _redis
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        await client.ping()
        _redis = client
        logger.info(f"✅ Redis connected: {REDIS_URL}")
    except Exception as exc:
        logger.warning(f"⚠️  Redis unavailable ({exc}) — using in-process cache fallback")
        _redis = None


async def close_cache() -> None:
    """Gracefully close Redis connection."""
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


# ── URL normalisation (shared helper) ─────────────────────────────────────────

def normalize_url(url: str) -> str:
    """Strip protocol / www / trailing slash for consistent cache keys."""
    url = url.strip().lower()
    for prefix in ("https://", "http://", "www."):
        if url.startswith(prefix):
            url = url[len(prefix):]
    return url.rstrip("/")


def _cache_key(url: str) -> str:
    return f"shadowtrace:investigation:{normalize_url(url)}"


# ── Public API ────────────────────────────────────────────────────────────────

async def get_cached(url: str) -> Optional[dict]:
    """Return a cached completed investigation for *url*, or None."""
    key = _cache_key(url)

    if _redis:
        try:
            raw = await _redis.get(key)
            if raw:
                logger.info(f"🟢 Redis cache HIT  → {key}")
                return json.loads(raw)
        except Exception as exc:
            logger.warning(f"Redis GET error: {exc}")
    else:
        raw = _local_cache.get(key)
        if raw:
            logger.info(f"🟢 Local cache HIT  → {key}")
            return json.loads(raw)

    return None


async def set_cached(url: str, report: dict) -> None:
    """Store a completed investigation in the cache."""
    key = _cache_key(url)
    value = json.dumps(report)

    if _redis:
        try:
            await _redis.set(key, value, ex=CACHE_TTL_SECONDS)
            logger.info(f"💾 Redis cached     → {key}  (TTL={CACHE_TTL_SECONDS}s)")
        except Exception as exc:
            logger.warning(f"Redis SET error: {exc}")
            _local_cache[key] = value   # fallback silently
    else:
        _local_cache[key] = value
        logger.info(f"💾 Local cached     → {key}")


async def invalidate(url: str) -> None:
    """Remove the cached entry for a URL (used by force_refresh)."""
    key = _cache_key(url)
    if _redis:
        try:
            await _redis.delete(key)
            logger.info(f"🗑️  Redis invalidated → {key}")
        except Exception as exc:
            logger.warning(f"Redis DEL error: {exc}")
    else:
        _local_cache.pop(key, None)
