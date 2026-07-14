"""Redis-backed stores for distributed deployments.

This module provides Redis-backed implementations of ContextStore, SignalStore,
and ChatSessionStore for horizontal scaling and persistence across restarts.

Design
------
* **Thread-safe**: Uses Redis atomic operations for consistency.
* **Distributed**: Multiple API replicas share the same state.
* **Persistent**: State survives process restarts.
* **TTL support**: Automatic expiration for session cleanup.
* **Drop-in replacement**: Same interface as in-memory implementations.

Usage
-----
::

    from ai_data_science_team.redis_stores import RedisContextStore, RedisSignalStore

    # For production with Redis
    context_store = RedisContextStore(redis_url="redis://localhost:6379/0")
    signal_store = RedisSignalStore(redis_url="redis://localhost:6379/0")

    # For development (falls back to in-memory)
    context_store = RedisContextStore()  # Uses in-memory fallback

Requirements
------------
For Redis mode, install: pip install redis

For Valkey (open-source alternative): pip install valkey-py
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

REDIS_AVAILABLE = False
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    pass


class RedisContextStore:
    """Redis-backed, distributed per-session context store.

    Drop-in replacement for ContextStore that uses Redis for persistence.
    Enables horizontal scaling with multiple API replicas.

    Parameters
    ----------
    redis_url : str | None
        Redis connection URL (e.g., "redis://localhost:6379/0").
        If None, falls back to in-memory implementation.
    key_prefix : str
        Prefix for all Redis keys to avoid collisions.
    session_ttl_seconds : int | None
        TTL for session data in seconds. None = no expiration.
    require_redis : bool
        If True and redis_url is provided but Redis is unavailable, raise an error
        instead of silently falling back to in-memory. Use this in production to
        prevent accidental state divergence in multi-replica deployments.
    **redis_kwargs
        Additional arguments passed to redis.Redis().

    Raises
    ------
    RuntimeError
        If require_redis=True and Redis is unavailable.

    Examples
    --------
    ::

        store = RedisContextStore(redis_url="redis://localhost:6379/0")
        sid = store.create_session(user_id="u1", workspace_id="ws1")
        store.set(sid, "raw_df", df)
        df = store.get(sid, "raw_df")
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        key_prefix: str = "ctx:",
        session_ttl_seconds: Optional[int] = None,
        require_redis: bool = False,
        **redis_kwargs,
    ) -> None:
        self._key_prefix = key_prefix
        self._session_ttl = session_ttl_seconds
        self._lock = threading.Lock()
        self._is_redis_mode = False

        if redis_url and REDIS_AVAILABLE:
            self._redis: Optional[redis.Redis] = redis.from_url(
                redis_url, **redis_kwargs
            )
            self._in_memory_fallback: Optional[Dict] = None
            self._is_redis_mode = True
            logger.info("RedisContextStore connected to Redis: %s", redis_url)
        elif redis_url and not REDIS_AVAILABLE:
            if require_redis:
                raise RuntimeError(
                    f"Redis is required (require_redis=True) but not available. "
                    f"Install with: pip install redis. "
                    f"This is a production deployment - in-memory fallback is disabled "
                    f"to prevent state divergence across replicas."
                )
            self._redis = None
            self._in_memory_fallback = {}
            logger.warning(
                "Redis not available (pip install redis). "
                "Falling back to in-memory store. WARNING: State will NOT be "
                "shared across replicas and will be lost on restart."
            )
        else:
            self._redis = None
            self._in_memory_fallback = {}
            logger.info("RedisContextStore using in-memory fallback")

    @property
    def is_distributed(self) -> bool:
        """Return True if using Redis backend (distributed mode)."""
        return self._is_redis_mode

    def _session_key(self, session_id: str) -> str:
        return f"{self._key_prefix}session:{session_id}"

    def _artifacts_key(self, session_id: str) -> str:
        return f"{self._key_prefix}artifacts:{session_id}"

    def _meta_key(self, session_id: str) -> str:
        return f"{self._key_prefix}meta:{session_id}"

    def create_session(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        scenario: str = "supervised",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        sid = session_id or str(uuid.uuid4())
        meta = {
            "session_id": sid,
            "user_id": user_id,
            "workspace_id": workspace_id,
            "scenario": scenario,
            "created_at": datetime.now(timezone.utc).isoformat(),
            **(metadata or {}),
        }

        if self._redis:
            pipe = self._redis.pipeline()
            pipe.hset(self._meta_key(sid), mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in meta.items()})
            pipe.delete(self._artifacts_key(sid))
            if self._session_ttl:
                pipe.expire(self._meta_key(sid), self._session_ttl)
                pipe.expire(self._artifacts_key(sid), self._session_ttl)
            pipe.execute()
        else:
            with self._lock:
                self._in_memory_fallback[sid] = {
                    "_meta": meta,
                    "_artifacts": [],
                }

        return sid

    def session_exists(self, session_id: str) -> bool:
        if self._redis:
            return bool(self._redis.exists(self._meta_key(session_id)))
        else:
            with self._lock:
                return session_id in self._in_memory_fallback

    def get_session(self, session_id: str) -> Dict[str, Any]:
        if self._redis:
            meta_raw = self._redis.hgetall(self._meta_key(session_id))
            if not meta_raw:
                raise KeyError(f"Session '{session_id}' does not exist.")
            meta = {k.decode() if isinstance(k, bytes) else k: self._parse_value(v) for k, v in meta_raw.items()}
            artifacts_raw = self._redis.lrange(self._artifacts_key(session_id), 0, -1)
            artifacts = [json.loads(a) for a in artifacts_raw]
            return {"_meta": meta, "_artifacts": artifacts}
        else:
            with self._lock:
                if session_id not in self._in_memory_fallback:
                    raise KeyError(f"Session '{session_id}' does not exist.")
                return dict(self._in_memory_fallback[session_id])

    def get_meta(self, session_id: str) -> Dict[str, Any]:
        if self._redis:
            meta_raw = self._redis.hgetall(self._meta_key(session_id))
            return {k.decode() if isinstance(k, bytes) else k: self._parse_value(v) for k, v in meta_raw.items()}
        else:
            with self._lock:
                return dict(self._in_memory_fallback.get(session_id, {}).get("_meta", {}))

    def update_meta(self, session_id: str, **kwargs: Any) -> None:
        if self._redis:
            pipe = self._redis.pipeline()
            for k, v in kwargs.items():
                pipe.hset(self._meta_key(session_id), k, json.dumps(v) if isinstance(v, (dict, list)) else str(v))
            if self._session_ttl:
                pipe.expire(self._meta_key(session_id), self._session_ttl)
            pipe.execute()
        else:
            with self._lock:
                if session_id in self._in_memory_fallback:
                    self._in_memory_fallback[session_id].setdefault("_meta", {}).update(kwargs)

    def clear_session(self, session_id: str) -> None:
        if self._redis:
            self._redis.delete(
                self._meta_key(session_id),
                self._artifacts_key(session_id),
                self._session_key(session_id),
            )
        else:
            with self._lock:
                self._in_memory_fallback.pop(session_id, None)

    def list_sessions(self) -> List[str]:
        if self._redis:
            pattern = f"{self._key_prefix}meta:*"
            keys = self._redis.keys(pattern)
            prefix_len = len(f"{self._key_prefix}meta:")
            return [k.decode()[prefix_len:] if isinstance(k, bytes) else k[prefix_len:] for k in keys]
        else:
            with self._lock:
                return list(self._in_memory_fallback.keys())

    def set(self, session_id: str, key: str, value: Any) -> None:
        if self._redis:
            serialized = json.dumps(value) if not isinstance(value, str) else value
            self._redis.hset(self._session_key(session_id), key, serialized)
            if self._session_ttl:
                self._redis.expire(self._session_key(session_id), self._session_ttl)
        else:
            with self._lock:
                if session_id not in self._in_memory_fallback:
                    self._in_memory_fallback[session_id] = {"_meta": {}, "_artifacts": []}
                self._in_memory_fallback[session_id][key] = value

    def get(self, session_id: str, key: str, default: Any = None) -> Any:
        if self._redis:
            value = self._redis.hget(self._session_key(session_id), key)
            if value is None:
                return default
            return self._parse_value(value)
        else:
            with self._lock:
                return self._in_memory_fallback.get(session_id, {}).get(key, default)

    def delete(self, session_id: str, key: str) -> None:
        if self._redis:
            self._redis.hdel(self._session_key(session_id), key)
        else:
            with self._lock:
                self._in_memory_fallback.get(session_id, {}).pop(key, None)

    def keys(self, session_id: str) -> List[str]:
        if self._redis:
            all_keys = self._redis.hkeys(self._session_key(session_id))
            result = []
            for k in all_keys:
                decoded = k.decode() if isinstance(k, bytes) else k
                if not decoded.startswith("_"):
                    result.append(decoded)
            return result
        else:
            with self._lock:
                return [k for k in self._in_memory_fallback.get(session_id, {}).keys() if not k.startswith("_")]

    def append_artifact(
        self,
        session_id: str,
        artifact_type: str,
        content: Any,
        step_id: Optional[str] = None,
        agent_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        record = {
            "artifact_type": artifact_type,
            "content": content,
            "step_id": step_id,
            "agent_name": agent_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if self._redis:
            self._redis.rpush(self._artifacts_key(session_id), json.dumps(record))
            if self._session_ttl:
                self._redis.expire(self._artifacts_key(session_id), self._session_ttl)
        else:
            with self._lock:
                if session_id not in self._in_memory_fallback:
                    self._in_memory_fallback[session_id] = {"_meta": {}, "_artifacts": []}
                self._in_memory_fallback[session_id]["_artifacts"].append(record)

        return record

    def get_artifacts(
        self,
        session_id: str,
        artifact_type: Optional[str] = None,
        step_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if self._redis:
            artifacts_raw = self._redis.lrange(self._artifacts_key(session_id), 0, -1)
            records = [json.loads(a) for a in artifacts_raw]
        else:
            with self._lock:
                records = list(self._in_memory_fallback.get(session_id, {}).get("_artifacts", []))

        if artifact_type:
            records = [r for r in records if r.get("artifact_type") == artifact_type]
        if step_id:
            records = [r for r in records if r.get("step_id") == step_id]

        return records

    def artifact_count(self, session_id: str) -> int:
        if self._redis:
            return self._redis.llen(self._artifacts_key(session_id))
        else:
            with self._lock:
                return len(self._in_memory_fallback.get(session_id, {}).get("_artifacts", []))

    @staticmethod
    def _parse_value(value: Union[str, bytes]) -> Any:
        if isinstance(value, bytes):
            value = value.decode()
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value


class RedisSignalStore:
    """Redis-backed, distributed signal store for workflow interventions.

    Drop-in replacement for SignalStore that uses Redis for persistence.
    Enables horizontal scaling with multiple API replicas.

    Parameters
    ----------
    redis_url : str | None
        Redis connection URL. If None, falls back to in-memory.
    key_prefix : str
        Prefix for all Redis keys.
    signal_ttl_seconds : int | None
        TTL for signals in seconds. None = no expiration.
    require_redis : bool
        If True and redis_url is provided but Redis is unavailable, raise an error
        instead of silently falling back to in-memory.
    **redis_kwargs
        Additional arguments passed to redis.Redis().

    Raises
    ------
    RuntimeError
        If require_redis=True and Redis is unavailable.

    Examples
    --------
    ::

        from ai_data_science_team.redis_stores import RedisSignalStore
        from ai_data_science_team.signals import WorkflowSignal, SignalType

        store = RedisSignalStore(redis_url="redis://localhost:6379/0")
        store.emit(WorkflowSignal(type=SignalType.SKIP, session_id="s1", step_id="step1"))
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        key_prefix: str = "sig:",
        signal_ttl_seconds: Optional[int] = None,
        require_redis: bool = False,
        **redis_kwargs,
    ) -> None:
        self._key_prefix = key_prefix
        self._signal_ttl = signal_ttl_seconds
        self._lock = threading.Lock()
        self._is_redis_mode = False

        if redis_url and REDIS_AVAILABLE:
            self._redis: Optional[redis.Redis] = redis.from_url(
                redis_url, **redis_kwargs
            )
            self._in_memory_fallback: Optional[Dict] = None
            self._is_redis_mode = True
            logger.info("RedisSignalStore connected to Redis: %s", redis_url)
        elif redis_url and not REDIS_AVAILABLE:
            if require_redis:
                raise RuntimeError(
                    f"Redis is required (require_redis=True) but not available. "
                    f"Install with: pip install redis. "
                    f"This is a production deployment - in-memory fallback is disabled."
                )
            self._redis = None
            self._in_memory_fallback = {}
            logger.warning(
                "Redis not available. Falling back to in-memory signal store. "
                "WARNING: Signals will NOT be shared across replicas."
            )
        else:
            self._redis = None
            self._in_memory_fallback = {}

    @property
    def is_distributed(self) -> bool:
        """Return True if using Redis backend (distributed mode)."""
        return self._is_redis_mode

    def _signals_key(self, session_id: str) -> str:
        return f"{self._key_prefix}signals:{session_id}"

    def _consumed_key(self, session_id: str) -> str:
        return f"{self._key_prefix}consumed:{session_id}"

    def emit(self, signal) -> Any:

        signal_dict = signal.to_dict()
        signal_json = json.dumps(signal_dict)

        if self._redis:
            pipe = self._redis.pipeline()
            pipe.rpush(self._signals_key(signal.session_id), signal_json)
            if self._signal_ttl:
                pipe.expire(self._signals_key(signal.session_id), self._signal_ttl)
            pipe.execute()
        else:
            with self._lock:
                self._in_memory_fallback.setdefault(signal.session_id, []).append(signal)

        return signal

    def pop_pending(self, session_id: str) -> List:
        from ai_data_science_team.signals import WorkflowSignal

        if self._redis:
            signals_raw = self._redis.lrange(self._signals_key(session_id), 0, -1)
            pending = []
            for sig_json in signals_raw:
                sig_dict = json.loads(sig_json)
                if not sig_dict.get("consumed", False):
                    sig_dict["consumed"] = True
                    pending.append(WorkflowSignal(**sig_dict))

            if pending:
                pipe = self._redis.pipeline()
                pipe.delete(self._signals_key(session_id))
                for sig in pending:
                    pipe.rpush(self._signals_key(session_id), json.dumps(sig.to_dict()))
                if self._signal_ttl:
                    pipe.expire(self._signals_key(session_id), self._signal_ttl)
                pipe.execute()

            return pending
        else:
            with self._lock:
                signals = self._in_memory_fallback.get(session_id, [])
                pending = [s for s in signals if not s.consumed]
                for s in pending:
                    s.consumed = True
                return pending

    def list_all(self, session_id: str) -> List:
        from ai_data_science_team.signals import WorkflowSignal

        if self._redis:
            signals_raw = self._redis.lrange(self._signals_key(session_id), 0, -1)
            return [WorkflowSignal(**json.loads(s)) for s in signals_raw]
        else:
            with self._lock:
                return list(self._in_memory_fallback.get(session_id, []))

    def clear(self, session_id: str) -> None:
        if self._redis:
            self._redis.delete(self._signals_key(session_id))
        else:
            with self._lock:
                self._in_memory_fallback.pop(session_id, None)

    def session_ids(self) -> List[str]:
        if self._redis:
            pattern = f"{self._key_prefix}signals:*"
            keys = self._redis.keys(pattern)
            prefix_len = len(f"{self._key_prefix}signals:")
            return [k.decode()[prefix_len:] if isinstance(k, bytes) else k[prefix_len:] for k in keys]
        else:
            with self._lock:
                return list(self._in_memory_fallback.keys())


class RedisChatSessionStore:
    """Redis-backed, distributed chat session store.

    Drop-in replacement for ChatSessionStore that uses Redis for persistence.
    Enables horizontal scaling with multiple API replicas.

    Note: DataFrames are NOT stored in Redis (too large). They remain in-memory
    per process. Users must re-upload after server restart (same as ChatGPT).

    Parameters
    ----------
    redis_url : str | None
        Redis connection URL. If None, falls back to in-memory.
    key_prefix : str
        Prefix for all Redis keys.
    session_ttl_seconds : int | None
        TTL for sessions in seconds. None = no expiration.
    **redis_kwargs
        Additional arguments passed to redis.Redis().
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        key_prefix: str = "chat:",
        session_ttl_seconds: Optional[int] = None,
        **redis_kwargs,
    ) -> None:
        self._key_prefix = key_prefix
        self._session_ttl = session_ttl_seconds
        self._lock = threading.Lock()
        self._df_cache: Dict[str, Dict[str, Any]] = {}

        if redis_url and REDIS_AVAILABLE:
            self._redis: Optional[redis.Redis] = redis.from_url(
                redis_url, **redis_kwargs
            )
            self._in_memory_fallback: Optional[Dict] = None
            logger.info("RedisChatSessionStore connected to Redis: %s", redis_url)
        else:
            self._redis = None
            self._in_memory_fallback = {}
            if redis_url and not REDIS_AVAILABLE:
                logger.warning(
                    "Redis not available. Falling back to in-memory chat session store."
                )

    def _session_key(self, session_id: str) -> str:
        return f"{self._key_prefix}session:{session_id}"

    def _messages_key(self, session_id: str) -> str:
        return f"{self._key_prefix}messages:{session_id}"

    def _datasets_key(self, session_id: str) -> str:
        return f"{self._key_prefix}datasets:{session_id}"

    def create(
        self,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        from ai_data_science_team.multiagents.chat_session import ChatSession

        sid = session_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        if self._redis:
            pipe = self._redis.pipeline()
            pipe.hset(self._session_key(sid), mapping={
                "session_id": sid,
                "created_at": now.isoformat(),
                "metadata": json.dumps(metadata or {}),
            })
            if self._session_ttl:
                pipe.expire(self._session_key(sid), self._session_ttl)
                pipe.expire(self._messages_key(sid), self._session_ttl)
                pipe.expire(self._datasets_key(sid), self._session_ttl)
            pipe.execute()
        else:
            with self._lock:
                self._in_memory_fallback[sid] = {
                    "session_id": sid,
                    "created_at": now,
                    "metadata": metadata or {},
                    "messages": [],
                    "datasets": {},
                }

        return ChatSession(session_id=sid, metadata=metadata or {}, created_at=now)

    def get(self, session_id: str):
        from ai_data_science_team.multiagents.chat_session import ChatSession, ChatMessage

        if self._redis:
            session_data = self._redis.hgetall(self._session_key(session_id))
            if not session_data:
                return None

            messages_raw = self._redis.lrange(self._messages_key(session_id), 0, -1)
            messages = [ChatMessage(**json.loads(m)) for m in messages_raw]

            with self._lock:
                datasets = dict(self._df_cache.get(session_id, {}))

            return ChatSession(
                session_id=session_id,
                messages=messages,
                datasets=datasets,
                created_at=datetime.fromisoformat(
                    session_data.get(b"created_at", session_data.get("created_at", b"")).decode()
                    if isinstance(session_data.get(b"created_at", session_data.get("created_at")), bytes)
                    else session_data.get("created_at", "")
                ) if session_data.get(b"created_at", session_data.get("created_at")) else datetime.now(timezone.utc),
                metadata=json.loads(
                    session_data.get(b"metadata", session_data.get("metadata", b"{}")).decode()
                    if isinstance(session_data.get(b"metadata", session_data.get("metadata")), bytes)
                    else session_data.get("metadata", "{}")
                ),
            )
        else:
            with self._lock:
                data = self._in_memory_fallback.get(session_id)
                if not data:
                    return None
                from ai_data_science_team.multiagents.chat_session import ChatSession
                return ChatSession(
                    session_id=data["session_id"],
                    messages=data.get("messages", []),
                    datasets=data.get("datasets", {}),
                    created_at=data.get("created_at", datetime.now(timezone.utc)),
                    metadata=data.get("metadata", {}),
                )

    def delete(self, session_id: str) -> bool:
        if self._redis:
            result = self._redis.delete(
                self._session_key(session_id),
                self._messages_key(session_id),
                self._datasets_key(session_id),
            )
            with self._lock:
                self._df_cache.pop(session_id, None)
            return result > 0
        else:
            with self._lock:
                return self._in_memory_fallback.pop(session_id, None) is not None

    def list_ids(self) -> List[str]:
        if self._redis:
            pattern = f"{self._key_prefix}session:*"
            keys = self._redis.keys(pattern)
            prefix_len = len(f"{self._key_prefix}session:")
            return [k.decode()[prefix_len:] if isinstance(k, bytes) else k[prefix_len:] for k in keys]
        else:
            with self._lock:
                return list(self._in_memory_fallback.keys())

    def clear(self) -> None:
        if self._redis:
            pattern = f"{self._key_prefix}*"
            keys = self._redis.keys(pattern)
            if keys:
                self._redis.delete(*keys)
            with self._lock:
                self._df_cache.clear()
        else:
            with self._lock:
                self._in_memory_fallback.clear()

    def __len__(self) -> int:
        return len(self.list_ids())

    def upload_dataset(self, session_id: str, name: str, df) -> None:

        with self._lock:
            if self._redis:
                if not self._redis.exists(self._session_key(session_id)):
                    raise KeyError(f"Session not found: {session_id}")
                self._redis.sadd(self._datasets_key(session_id), name)
                if self._session_ttl:
                    self._redis.expire(self._datasets_key(session_id), self._session_ttl)
            else:
                if session_id not in self._in_memory_fallback:
                    raise KeyError(f"Session not found: {session_id}")

            if session_id not in self._df_cache:
                self._df_cache[session_id] = {}
            self._df_cache[session_id][name] = df

    def get_datasets(self, session_id: str) -> Dict[str, Any]:
        if self._redis:
            if not self._redis.exists(self._session_key(session_id)):
                raise KeyError(f"Session not found: {session_id}")
        else:
            with self._lock:
                if session_id not in self._in_memory_fallback:
                    raise KeyError(f"Session not found: {session_id}")

        with self._lock:
            return dict(self._df_cache.get(session_id, {}))

    def add_message(self, session_id: str, message) -> None:

        message_dict = {
            "role": message.role,
            "content": message.content,
            "artifact": message.artifact,
            "agent_used": message.agent_used,
            "timestamp": message.timestamp.isoformat() if hasattr(message.timestamp, "isoformat") else message.timestamp,
        }

        if self._redis:
            result = self._redis.rpush(self._messages_key(session_id), json.dumps(message_dict))
            if result == 0:
                raise KeyError(f"Session not found: {session_id}")
            if self._session_ttl:
                self._redis.expire(self._messages_key(session_id), self._session_ttl)
        else:
            with self._lock:
                if session_id not in self._in_memory_fallback:
                    raise KeyError(f"Session not found: {session_id}")
                self._in_memory_fallback[session_id]["messages"].append(message)

    def get_history(self, session_id: str) -> List:
        from ai_data_science_team.multiagents.chat_session import ChatMessage

        if self._redis:
            messages_raw = self._redis.lrange(self._messages_key(session_id), 0, -1)
            if not messages_raw and not self._redis.exists(self._session_key(session_id)):
                raise KeyError(f"Session not found: {session_id}")
            return [ChatMessage(**json.loads(m)) for m in messages_raw]
        else:
            with self._lock:
                if session_id not in self._in_memory_fallback:
                    raise KeyError(f"Session not found: {session_id}")
                return list(self._in_memory_fallback[session_id].get("messages", []))


__all__ = [
    "RedisContextStore",
    "RedisSignalStore",
    "RedisChatSessionStore",
    "REDIS_AVAILABLE",
]
