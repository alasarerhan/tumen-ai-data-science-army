from __future__ import annotations

"""Agent result caching for cost optimization.

Provides Redis-backed and in-memory caching for LangChain agent outputs.
Reduces OpenAI API costs by caching identical prompts.

Usage
-----
::

    from ai_data_science_team.utils.agent_cache import AgentCache, cached_agent_call  # noqa: E402, F401

    # Initialize cache
    cache = AgentCache(redis_url="redis://localhost:6379/0", ttl_seconds=3600)

    # Cache key from inputs
    key = cache.hash_inputs(agent_name="sql_agent", instruction="SELECT * FROM users", context={})

    # Check cache
    cached = cache.get(key)
    if cached:
        return cached

    # Or use decorator
    @cached_agent_call(ttl_seconds=7200)
    def my_agent_call(agent_name, instruction, context):
        # ... expensive LLM call ...
        return result
"""

import hashlib  # noqa: E402, F401
import json  # noqa: E402, F401
import logging  # noqa: E402, F401
import threading  # noqa: E402, F401
import time  # noqa: E402, F401
from functools import wraps  # noqa: E402, F401
from typing import Any, Callable, Dict, Optional  # noqa: E402, F401

logger = logging.getLogger(__name__)

try:
    from platform_api.tenant_context import get_current_tenant_id  # noqa: E402, F401
except ImportError:  # pragma: no cover - platform API may be unavailable in standalone use
    def get_current_tenant_id() -> Any:
        return None

REDIS_AVAILABLE = False
try:
    import redis  # noqa: E402, F401
    REDIS_AVAILABLE = True
except ImportError:
    pass


class AgentCache:
    """Redis-backed or in-memory cache for agent results.

    Parameters
    ----------
    redis_url : str | None
        Redis connection URL. If None, uses in-memory cache.
    key_prefix : str
        Prefix for all cache keys.
    ttl_seconds : int
        Default TTL for cached entries (default: 3600 = 1 hour).
    max_memory_entries : int
        Maximum entries for in-memory fallback (default: 1000).
    version : str
        Cache version for invalidation. Change this when agent behavior changes
        (e.g., model upgrade, prompt changes) to invalidate all cached results.

    Cache Versioning
    ----------------
    The version parameter is included in all cache keys. When you change the
    version, all existing cached results become invalid. Use this when:
    - Upgrading the underlying LLM model
    - Changing agent prompts or instructions
    - Fixing bugs in agent output parsing
    - Modifying agent behavior

    Example:
        # Old cache with version "v1"
        cache = AgentCache(version="v1")

        # After model upgrade, invalidate all old results
        cache = AgentCache(version="v2")  # All v1 results are now invalid
    """

    CACHE_VERSION = "v1"

    def __init__(
        self,
        redis_url: Optional[str] = None,
        key_prefix: str = "agent_cache:",
        ttl_seconds: int = 3600,
        max_memory_entries: int = 1000,
        version: Optional[str] = None,
    ) -> None:
        self._key_prefix = key_prefix
        self._ttl = ttl_seconds
        self._max_memory_entries = max_memory_entries
        self._version = version or self.CACHE_VERSION
        self._lock = threading.Lock()
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self._memory_access: Dict[str, float] = {}

        if redis_url and REDIS_AVAILABLE:
            self._redis: Optional[redis.Redis] = redis.from_url(redis_url)
            logger.info("AgentCache connected to Redis: %s (version=%s)", redis_url, self._version)
        else:
            self._redis = None
            if redis_url and not REDIS_AVAILABLE:
                logger.warning(
                    "Redis not available (pip install redis). "
                    "Using in-memory agent cache."
                )

    def _tenant_namespace(self, tenant_id: Any | None = None) -> str:
        if tenant_id is None:
            tenant_id = get_current_tenant_id()
        return f"tenant:{tenant_id}:" if tenant_id is not None else ""

    def _cache_key(self, key: str) -> str:
        tenant_namespace = self._tenant_namespace()
        return f"{self._key_prefix}{tenant_namespace}{self._version}:{key}"

    def _cache_pattern(self, tenant_id: Any | None = None) -> str:
        tenant_namespace = self._tenant_namespace(tenant_id)
        return f"{self._key_prefix}{tenant_namespace}*"

    @property
    def version(self) -> str:
        """Get the current cache version."""
        return self._version

    def set_version(self, version: str) -> None:
        """Set a new cache version, invalidating all previous cached results.

        WARNING: This does not delete old cached entries, but makes them
        inaccessible. Use clear() first if you want to free memory.

        Parameters
        ----------
        version : str
            New cache version string.
        """
        self._version = version
        logger.info("Cache version set to: %s", version)

    def hash_inputs(
        self,
        agent_name: str,
        instruction: str,
        context: Optional[Dict[str, Any]] = None,
        **extra: Any,
    ) -> str:
        """Generate deterministic cache key from agent inputs.

        Parameters
        ----------
        agent_name : str
            Name of the agent.
        instruction : str
            The instruction/prompt sent to the agent.
        context : dict | None
            Additional context (will be JSON-serialized).
        **extra : Any
            Additional parameters to include in hash.

        Returns
        -------
        str
            SHA256 hash key for caching.
        """
        payload = {
            "agent": agent_name,
            "instruction": instruction,
            "context": context or {},
            "version": self._version,
            **extra,
        }
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:32]

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached result.

        NOTE: For in-memory backend, this method updates LRU tracking metadata.
        This is a read operation that causes a write to _memory_access dict.
        While protected by a lock, high-concurrency scenarios may experience
        contention. For production high-throughput use cases, prefer Redis backend.

        Parameters
        ----------
        key : str
            Cache key from hash_inputs().

        Returns
        -------
        dict | None
            Cached result or None if not found/expired/failed.
        """
        full_key = self._cache_key(key)

        if self._redis:
            try:
                cached = self._redis.get(full_key)
                if cached:
                    logger.debug("Agent cache HIT: %s", key[:16])
                    return json.loads(cached)
                return None
            except Exception as e:
                logger.warning("Redis cache get failed for key %s: %s", key[:16], e)
                return None

        with self._lock:
            entry = self._memory_cache.get(full_key)
            if entry:
                if time.time() - entry.get("_timestamp", 0) < self._ttl:
                    self._memory_access[full_key] = time.time()
                    logger.debug("Agent cache HIT (memory): %s", key[:16])
                    return {k: v for k, v in entry.items() if not k.startswith("_")}
                else:
                    del self._memory_cache[full_key]
                    self._memory_access.pop(full_key, None)
            return None

    def set(
        self,
        key: str,
        result: Dict[str, Any],
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """Store result in cache.

        Parameters
        ----------
        key : str
            Cache key from hash_inputs().
        result : dict
            Agent result to cache.
        ttl_seconds : int | None
            Override TTL for this entry.

        Returns
        -------
        bool
            True if cache set succeeded, False if it failed.
        """
        full_key = self._cache_key(key)
        ttl = ttl_seconds or self._ttl

        if self._redis:
            try:
                self._redis.setex(full_key, ttl, json.dumps(result, default=str))
                logger.debug("Agent cache SET: %s (TTL=%ds)", key[:16], ttl)
                return True
            except Exception as e:
                logger.warning("Redis cache set failed for key %s: %s", key[:16], e)
                return False

        with self._lock:
            if len(self._memory_cache) >= self._max_memory_entries:
                self._evict_lru()
            self._memory_cache[full_key] = {
                **result,
                "_timestamp": time.time(),
            }
            self._memory_access[full_key] = time.time()
            logger.debug("Agent cache SET (memory): %s (TTL=%ds)", key[:16], ttl)

    def _evict_lru(self) -> None:
        """Evict least recently used entries when memory cache is full."""
        if not self._memory_access:
            return
        lru_key = min(self._memory_access, key=self._memory_access.get)
        self._memory_cache.pop(lru_key, None)
        self._memory_access.pop(lru_key, None)

    def delete(self, key: str) -> bool:
        """Remove entry from cache.

        Returns
        -------
        bool
            True if deletion succeeded, False if it failed.
        """
        full_key = self._cache_key(key)

        if self._redis:
            try:
                self._redis.delete(full_key)
                return True
            except Exception as e:
                logger.warning("Redis cache delete failed for key %s: %s", key[:16], e)
                return False
        else:
            with self._lock:
                self._memory_cache.pop(full_key, None)
                self._memory_access.pop(full_key, None)
            return True

    def clear(self) -> None:
        """Clear all cached entries."""
        if self._redis:
            try:
                pattern = self._cache_pattern()
                keys = self._redis.keys(pattern)
                if keys:
                    self._redis.delete(*keys)
            except Exception as e:
                logger.warning("Redis cache clear failed: %s", e)
        else:
            with self._lock:
                pattern_prefix = self._cache_pattern()[:-1]
                keys_to_delete = [
                    cache_key for cache_key in self._memory_cache
                    if cache_key.startswith(pattern_prefix)
                ]
                for cache_key in keys_to_delete:
                    self._memory_cache.pop(cache_key, None)
                    self._memory_access.pop(cache_key, None)

    def clear_tenant(self, tenant_id: Any) -> int:
        """Clear cached entries for an explicit tenant namespace."""
        pattern = self._cache_pattern(tenant_id)
        if self._redis:
            try:
                keys = list(self._redis.scan_iter(match=pattern))
                if keys:
                    self._redis.delete(*keys)
                return len(keys)
            except Exception as e:
                logger.warning("Redis tenant cache clear failed for tenant %s: %s", tenant_id, e)
                return 0

        pattern_prefix = pattern[:-1]
        deleted = 0
        with self._lock:
            keys_to_delete = [
                cache_key for cache_key in self._memory_cache
                if cache_key.startswith(pattern_prefix)
            ]
            for cache_key in keys_to_delete:
                self._memory_cache.pop(cache_key, None)
                self._memory_access.pop(cache_key, None)
                deleted += 1
        return deleted

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if self._redis:
            try:
                pattern = self._cache_pattern()
                keys = self._redis.keys(pattern)
                return {
                    "backend": "redis",
                    "entries": len(keys),
                    "key_prefix": self._key_prefix,
                    "error": None,
                }
            except Exception as e:
                logger.warning("Redis cache stats failed: %s", e)
                return {
                    "backend": "redis",
                    "entries": 0,
                    "key_prefix": self._key_prefix,
                    "error": str(e),
                }

        return {
            "backend": "memory",
            "entries": len(
                [
                    cache_key
                    for cache_key in self._memory_cache
                    if cache_key.startswith(self._cache_pattern()[:-1])
                ]
            ),
            "max_entries": self._max_memory_entries,
            "error": None,
        }


_global_cache: Optional[AgentCache] = None
_global_cache_lock = threading.Lock()


def get_agent_cache(
    redis_url: Optional[str] = None,
    ttl_seconds: int = 3600,
) -> AgentCache:
    """Get or create global agent cache instance.

    Parameters
    ----------
    redis_url : str | None
        Redis URL for distributed caching.
    ttl_seconds : int
        Default TTL for cached entries.

    Returns
    -------
    AgentCache
        Global cache instance.
    """
    global _global_cache
    if _global_cache is None:
        with _global_cache_lock:
            if _global_cache is None:
                _global_cache = AgentCache(redis_url=redis_url, ttl_seconds=ttl_seconds)
    return _global_cache


def reset_agent_cache() -> None:
    """Reset the global agent cache singleton.

    WARNING: This function is for TESTING ONLY. Do not use in production.

    This function clears the global agent cache singleton, allowing tests
    to start with a fresh state. Using this in production could cause
    stale cache misses and inconsistent behavior.

    Usage in tests:
        @pytest.fixture(autouse=True)
        def reset_caches():
            from ai_data_science_team.utils.agent_cache import reset_agent_cache  # noqa: E402, F401
            reset_agent_cache()
            yield
            reset_agent_cache()
    """
    global _global_cache
    with _global_cache_lock:
        if _global_cache is not None:
            _global_cache._memory_cache.clear()
            _global_cache._memory_access.clear()
        _global_cache = None


def cached_agent_call(
    ttl_seconds: int = 3600,
    redis_url: Optional[str] = None,
    cache_key_params: Optional[list] = None,
) -> Callable:
    """Decorator to cache agent call results.

    Parameters
    ----------
    ttl_seconds : int
        Cache TTL in seconds.
    redis_url : str | None
        Redis URL for distributed caching.
    cache_key_params : list | None
        List of parameter names to include in cache key.
        If None, uses all parameters.

    Returns
    -------
    Callable
        Decorated function.

    Note
    ----
    To bypass cache for a specific call, pass ``cache_bust=True`` as a keyword
    argument to the decorated function. This will force a fresh result and
    update the cache.

    Examples
    --------
    ::

        @cached_agent_call(ttl_seconds=7200)
        def call_sql_agent(agent_name, instruction, context):
            # ... expensive LLM call ...
            return result

        # Normal cached call
        result = call_sql_agent("sql_agent", "SELECT * FROM users", {})

        # Force fresh result (bypass cache)
        result = call_sql_agent("sql_agent", "SELECT * FROM users", {}, cache_bust=True)
    """
    cache = get_agent_cache(redis_url=redis_url, ttl_seconds=ttl_seconds)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            cache_bust = kwargs.pop("cache_bust", False)

            if cache_key_params:
                key_data = {
                    p: kwargs.get(p, args[i] if i < len(args) else None)
                    for i, p in enumerate(cache_key_params)
                }
            else:
                key_data = {
                    "args": args,
                    "kwargs": {k: v for k, v in kwargs.items()},
                }

            key = cache.hash_inputs(
                agent_name=func_name,
                instruction=json.dumps(key_data, sort_keys=True, default=str),
            )

            if not cache_bust:
                cached = cache.get(key)
                if cached is not None:
                    return cached.get("result")

            result = func(*args, **kwargs)

            if result is not None:
                cache.set(key, {"result": result}, ttl_seconds=ttl_seconds)

            return result

        return wrapper
    return decorator


__all__ = [
    "AgentCache",
    "get_agent_cache",
    "reset_agent_cache",
    "cached_agent_call",
    "REDIS_AVAILABLE",
]
