"""
Redis cache and session management for Kinetic Ledger.

Provides:
- A lazy-initialized Redis client (sync + async).
- Generic JSON cache helpers (get/set/delete) with TTL support.
- Decorators for caching async function results.
- A session/token store built on Redis with expiry.
- Connectivity checks for health endpoints.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from functools import wraps
from typing import Any, Awaitable, Callable, Dict, Optional, TypeVar, Union

try:
    import redis
    from redis import Redis
    from redis.asyncio import Redis as AsyncRedis
    from redis.exceptions import RedisError
    REDIS_AVAILABLE = True
except ImportError:  # pragma: no cover - dependency not installed
    Redis = Any  # type: ignore
    AsyncRedis = Any  # type: ignore
    RedisError = Exception
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)

T = TypeVar("T")

# =============================================================================
# Configuration
# =============================================================================

# Docker compose uses the service name `redis`; local dev can override to
# localhost by setting REDIS_URL in the environment.
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

REDIS_DEFAULT_TTL: int = int(os.getenv("REDIS_DEFAULT_TTL", "300"))  # 5 minutes
REDIS_CACHE_PREFIX: str = os.getenv("REDIS_CACHE_PREFIX", "kinetic:")
REDIS_SESSION_PREFIX: str = os.getenv("REDIS_SESSION_PREFIX", "kinetic:session:")
REDIS_LOCK_PREFIX: str = os.getenv("REDIS_LOCK_PREFIX", "kinetic:lock:")
REDIS_RATE_PREFIX: str = os.getenv("REDIS_RATE_PREFIX", "kinetic:rate:")

# Socket-level timeouts to fail fast instead of hanging requests.
REDIS_SOCKET_TIMEOUT: float = float(os.getenv("REDIS_SOCKET_TIMEOUT", "5.0"))
REDIS_SOCKET_CONNECT_TIMEOUT: float = float(
    os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", "5.0")
)


# =============================================================================
# Client Factory (lazy singleton)
# =============================================================================

_redis_client: Optional[Redis] = None
_redis_async_client: Optional[AsyncRedis] = None
_redis_connection_lock = None

def _get_connection_lock() -> Any:
    """Return a process-wide lock for lazy client initialization."""
    global _redis_connection_lock
    if _redis_connection_lock is None:
        _redis_connection_lock = threading.Lock()
    return _redis_connection_lock


def get_redis_client(**kwargs: Any) -> Redis:
    """Return a lazy-initialized sync Redis client.

    Reuses a single client per process. Callers may pass connection
    overrides (e.g. ``decode_responses=False``) only on first creation.
    """
    global _redis_client
    if _redis_client is None:
        with _get_connection_lock():
            if _redis_client is None:
                client_kwargs = {
                    "url": REDIS_URL,
                    "decode_responses": True,
                    "socket_timeout": REDIS_SOCKET_TIMEOUT,
                    "socket_connect_timeout": REDIS_SOCKET_CONNECT_TIMEOUT,
                    "health_check_interval": 30,
                }
                client_kwargs.update(kwargs)
                _redis_client = redis.Redis.from_url(**client_kwargs)
                # Ping to validate the connection eagerly.
                _redis_client.ping()
                logger.info("Connected to Redis at %s", REDIS_URL)
    return _redis_client


def get_async_redis_client(**kwargs: Any) -> AsyncRedis:
    """Return a lazy-initialized async Redis client."""
    global _redis_async_client
    if _redis_async_client is None:
        client_kwargs = {
            "url": REDIS_URL,
            "decode_responses": True,
            "socket_timeout": REDIS_SOCKET_TIMEOUT,
            "socket_connect_timeout": REDIS_SOCKET_CONNECT_TIMEOUT,
            "health_check_interval": 30,
        }
        client_kwargs.update(kwargs)
        _redis_async_client = redis.asyncio.from_url(**client_kwargs)
        logger.info("Created async Redis client for %s", REDIS_URL)
    return _redis_async_client


# =============================================================================
# Key Helpers
# =============================================================================

def build_key(*parts: Union[str, int]) -> str:
    """Join key parts with ``:`` and prefix with the cache namespace."""
    return REDIS_CACHE_PREFIX + ":".join(str(p) for p in parts)


def build_session_key(session_id: str) -> str:
    """Return a namespaced session key."""
    return f"{REDIS_SESSION_PREFIX}{session_id}"


def build_lock_key(name: str) -> str:
    """Return a namespaced lock key."""
    return f"{REDIS_LOCK_PREFIX}{name}"


def build_rate_limit_key(name: str, identifier: str = "") -> str:
    """Return a namespaced rate-limit key."""
    return f"{REDIS_RATE_PREFIX}{name}:{identifier}"


# =============================================================================
# Sync JSON Cache Helpers
# =============================================================================

def cache_get(key: str, default: T = None) -> T:
    """Fetch a JSON value from Redis, returning ``default`` when missing/error."""
    if not REDIS_AVAILABLE:
        logger.warning("Redis not installed; cache_get returning default.")
        return default
    try:
        client = get_redis_client()
        raw = client.get(key)
        if raw is None:
            return default
        return json.loads(raw)
    except (RedisError, json.JSONDecodeError, Exception) as exc:
        logger.warning("cache_get(%r) failed: %s", key, exc)
        return default


def cache_set(key: str, value: Any, ttl: Optional[int] = None) -> bool:
    """Store a JSON-serializable value with an optional TTL (seconds)."""
    if not REDIS_AVAILABLE:
        logger.warning("Redis not installed; cache_set skipped.")
        return False
    try:
        client = get_redis_client()
        serialized = json.dumps(value)
        ttl_seconds = ttl if ttl is not None else REDIS_DEFAULT_TTL
        return bool(client.set(key, serialized, ex=ttl_seconds))
    except (RedisError, TypeError, ValueError, Exception) as exc:
        logger.warning("cache_set(%r) failed: %s", key, exc)
        return False


def cache_delete(key: str) -> bool:
    """Delete a key from Redis. Returns ``True`` if it existed."""
    if not REDIS_AVAILABLE:
        return False
    try:
        client = get_redis_client()
        return bool(client.delete(key))
    except (RedisError, Exception) as exc:
        logger.warning("cache_delete(%r) failed: %s", key, exc)
        return False


def cache_exists(key: str) -> bool:
    """Return True if a key exists in Redis."""
    if not REDIS_AVAILABLE:
        return False
    try:
        client = get_redis_client()
        return bool(client.exists(key))
    except (RedisError, Exception) as exc:
        logger.warning("cache_exists(%r) failed: %s", key, exc)
        return False


def cache_ttl(key: str) -> int:
    """Return the remaining TTL in seconds (-1 = no expiry, -2 = missing)."""
    if not REDIS_AVAILABLE:
        return -2
    try:
        client = get_redis_client()
        return int(client.ttl(key))
    except (RedisError, Exception) as exc:
        logger.warning("cache_ttl(%r) failed: %s", key, exc)
        return -2


# =============================================================================
# Session / Token Store
# =============================================================================

def create_session(
    session_id: str,
    data: Dict[str, Any],
    ttl: Optional[int] = None,
) -> bool:
    """Store session data as a JSON hash with expiry."""
    return cache_set(build_session_key(session_id), data, ttl=ttl)


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve session data by session id."""
    result = cache_get(build_session_key(session_id), default=None)
    if result is None:
        return None
    if not isinstance(result, dict):
        logger.warning("Session %s is not a dict; ignoring.", session_id)
        return None
    return result


def delete_session(session_id: str) -> bool:
    """Delete a session by session id."""
    return cache_delete(build_session_key(session_id))


def touch_session(session_id: str, ttl: Optional[int] = None) -> bool:
    """Refresh the TTL of an existing session key."""
    if not REDIS_AVAILABLE:
        return False
    try:
        client = get_redis_client()
        key = build_session_key(session_id)
        return bool(client.expire(key, ttl if ttl is not None else REDIS_DEFAULT_TTL))
    except (RedisError, Exception) as exc:
        logger.warning("touch_session(%r) failed: %s", session_id, exc)
        return False


def is_session_active(session_id: str) -> bool:
    """Return True if a session exists and is unexpired."""
    return cache_exists(build_session_key(session_id))


# =============================================================================
# Distributed Locks (SET NX EX pattern)
# =============================================================================

def acquire_lock(name: str, ttl: int = 30, token: Optional[str] = None) -> Optional[str]:
    """Acquire a distributed lock; returns the lock token on success.

    Uses SET NX EX which is atomic and safe with multiple workers.
    """
    if not REDIS_AVAILABLE:
        logger.warning("Redis not installed; acquire_lock returning None.")
        return None
    try:
        client = get_redis_client()
        lock_token = token or f"{os.getpid()}:{time.time_ns()}"
        acquired = client.set(build_lock_key(name), lock_token, nx=True, ex=ttl)
        if acquired:
            return lock_token
        return None
    except (RedisError, Exception) as exc:
        logger.warning("acquire_lock(%r) failed: %s", name, exc)
        return None


def release_lock(name: str, token: str) -> bool:
    """Release a lock we own (token match prevents stealing other holders' locks)."""
    if not REDIS_AVAILABLE:
        return False
    try:
        client = get_redis_client()
        key = build_lock_key(name)

        # Lua script atomically deletes only if the token matches.
        release_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        result = client.eval(release_script, 1, key, token)
        return bool(result)
    except (RedisError, Exception) as exc:
        logger.warning("release_lock(%r) failed: %s", name, exc)
        return False


# =============================================================================
# Rate Limiting (fixed window)
# =============================================================================

def rate_limit(
    name: str,
    identifier: str,
    max_requests: int,
    window_seconds: int = 60,
) -> tuple[bool, int, int]:
    """Increment a fixed-window counter and report if the limit is exceeded.

    Returns ``(allowed, count, remaining_ttl)``.
    """
    if not REDIS_AVAILABLE:
        return True, 0, 0
    key = build_rate_limit_key(name, identifier)
    try:
        client = get_redis_client()
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds, nx=True)
        count, _ = pipe.execute()
        allowed = int(count) <= max_requests
        return allowed, int(count), int(client.ttl(key))
    except (RedisError, Exception) as exc:
        logger.warning("rate_limit(%r) failed: %s", key, exc)
        return True, 0, 0


# =============================================================================
# Async JSON Cache Helpers
# =============================================================================

async def async_cache_get(key: str, default: T = None) -> T:
    """Async fetch of a JSON value from Redis."""
    if not REDIS_AVAILABLE:
        return default
    try:
        client = get_async_redis_client()
        raw = await client.get(key)
        if raw is None:
            return default
        return json.loads(raw)
    except Exception as exc:
        logger.warning("async_cache_get(%r) failed: %s", key, exc)
        return default


async def async_cache_set(
    key: str, value: Any, ttl: Optional[int] = None
) -> bool:
    """Async store of a JSON value with optional TTL."""
    if not REDIS_AVAILABLE:
        return False
    try:
        client = get_async_redis_client()
        serialized = json.dumps(value)
        ttl_seconds = ttl if ttl is not None else REDIS_DEFAULT_TTL
        return bool(await client.set(key, serialized, ex=ttl_seconds))
    except Exception as exc:
        logger.warning("async_cache_set(%r) failed: %s", key, exc)
        return False


async def async_cache_delete(key: str) -> bool:
    """Async delete of a key from Redis."""
    if not REDIS_AVAILABLE:
        return False
    try:
        client = get_async_redis_client()
        return bool(await client.delete(key))
    except Exception as exc:
        logger.warning("async_cache_delete(%r) failed: %s", key, exc)
        return False


# =============================================================================
# Async Function Cache Decorator
# =============================================================================

def cached(
    ttl: Optional[int] = None,
    key_builder: Optional[Callable[..., str]] = None,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator that caches the result of an async function in Redis.

    Usage:
        ```python
        @cached(ttl=60)
        async def get_motion(motion_id: str) -> dict:
            ...
        ```
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            cache_key = (
                key_builder(*args, **kwargs)
                if key_builder
                else build_key(func.__name__, *args, *sorted(kwargs.items()))
            )
            cached_value = await async_cache_get(cache_key)
            if cached_value is not None:
                return cached_value

            result = await func(*args, **kwargs)
            await async_cache_set(cache_key, result, ttl=ttl)
            return result

        return wrapper

    return decorator


# =============================================================================
# Connectivity & Lifecycle
# =============================================================================

def check_redis_connection() -> bool:
    """Return True if Redis is reachable (used by health endpoints)."""
    if not REDIS_AVAILABLE:
        logger.warning("redis package not installed; connection check failed.")
        return False
    try:
        client = get_redis_client()
        return bool(client.ping())
    except Exception as exc:
        logger.warning("Redis connectivity check failed: %s", exc)
        return False


async def async_check_redis_connection() -> bool:
    """Async version of the Redis connectivity check."""
    if not REDIS_AVAILABLE:
        return False
    try:
        client = get_async_redis_client()
        return bool(await client.ping())
    except Exception as exc:
        logger.warning("Async Redis connectivity check failed: %s", exc)
        return False


def close_redis() -> None:
    """Close the sync Redis client (e.g. on application shutdown)."""
    global _redis_client
    if _redis_client is not None:
        try:
            _redis_client.close()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Error closing Redis client: %s", exc)
        _redis_client = None


async def async_close_redis() -> None:
    """Close the async Redis client (e.g. on application shutdown)."""
    global _redis_async_client
    if _redis_async_client is not None:
        try:
            await _redis_async_client.aclose()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Error closing async Redis client: %s", exc)
        _redis_async_client = None