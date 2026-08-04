from __future__ import annotations

"""ChatSession — per-session state for the AI Workspace (M21).

Manages chat message history and uploaded DataFrames for a conversation
session.

Two store implementations ship here:

``ChatSessionStore``
    Thread-safe **in-memory** store.  Zero external dependencies; good for
    tests and single-process deployments.

``MongoChatSessionStore``
    **MongoDB-backed** persistent store (pymongo sync driver).
    Messages and session metadata are stored as embedded documents inside a
    single ``chat_sessions`` collection.  DataFrames are **not** stored in
    MongoDB (binary data is kept in a local cache per process — the user
    re-uploads on a new server instance, exactly like ChatGPT behaviour).

MongoDB document schema
-----------------------
::

    {
      "_id": "<session-uuid>",
      "metadata": {"user_id": "...", ...},
      "created_at": ISODate,
      "expires_at": ISODate | null,   ← TTL index field
      "dataset_names": ["sales", "churn"],   ← names only
      "messages": [
        {
          "role": "user" | "assistant",
          "content": "...",
          "artifact":  {...} | null,
          "agent_used": "..." | null,
          "timestamp": ISODate
        },
        ...
      ]
    }

Both stores expose the **same public interface** so ``ChatWorkspace`` and
all tests are fully portable between implementations.

Design notes
------------
* Plain Python — no LangGraph, no LLM calls.
* ``ChatSessionStore`` / ``MongoChatSessionStore`` are the single owners of
  all session state; downstream agents must **not** hold direct references.
"""

import threading  # noqa: E402, F401
import uuid  # noqa: E402, F401
from dataclasses import dataclass, field  # noqa: E402, F401
from datetime import datetime, timezone  # noqa: E402, F401
from typing import Any, Dict, List, Literal, Optional  # noqa: E402, F401

import pandas as pd  # noqa: E402, F401

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ChatMessage:
    """A single message in a chat session.

    Parameters
    ----------
    role : "user" | "assistant"
        Who sent the message.
    content : str
        The message text (plain text or markdown).
    artifact : dict | None
        Serialised artifact produced by the assistant, e.g.
        ``{"type": "table", "records": [...], "columns": [...]}`` or
        ``{"type": "chart", ...}``.
    agent_used : str | None
        Name of the agent that generated this response (assistant only).
    timestamp : datetime
        UTC creation time; auto-set on construction.
    """

    role: Literal["user", "assistant"]
    content: str
    artifact: Optional[Dict[str, Any]] = None
    agent_used: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ChatSession:
    """State for a single conversation session.

    Parameters
    ----------
    session_id : str
        Unique identifier.
    messages : list[ChatMessage]
        Ordered message history.
    datasets : dict[str, pd.DataFrame]
        DataFrames uploaded by the user, keyed by filename / alias.
    created_at : datetime
        UTC creation timestamp.
    metadata : dict
        Arbitrary caller-supplied key/value pairs (user_id, tags, etc.).
    """

    session_id: str
    messages: List[ChatMessage] = field(default_factory=list)
    datasets: Dict[str, pd.DataFrame] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Session store
# ---------------------------------------------------------------------------


class ChatSessionStore:
    """Thread-safe, in-memory store for :class:`ChatSession` objects.

    For production deployments replace the in-memory ``_sessions`` dict
    with a PostgreSQL / Redis-backed implementation while keeping the same
    public interface.

    Examples
    --------
    ::

        store = ChatSessionStore()
        session = store.create()
        store.upload_dataset(session.session_id, "sales", df)
        store.add_message(session.session_id, ChatMessage(role="user", content="hi"))
        history = store.get_history(session.session_id)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: Dict[str, ChatSession] = {}

    # ------------------------------------------------------------------ sessions

    def create(
        self,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ChatSession:
        """Create and persist a new session, then return it.

        Parameters
        ----------
        session_id : str | None
            Explicit id; a UUID4 is generated when *None*.
        metadata : dict | None
            Arbitrary metadata stored on the session.
        """
        sid = session_id or str(uuid.uuid4())
        session = ChatSession(
            session_id=sid,
            metadata=metadata or {},
        )
        with self._lock:
            self._sessions[sid] = session
        return session

    def get(self, session_id: str) -> Optional[ChatSession]:
        """Return the session or *None* if not found."""
        with self._lock:
            return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        """Delete a session.  Returns *True* if it existed."""
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def list_ids(self) -> List[str]:
        """Return all active session ids."""
        with self._lock:
            return list(self._sessions.keys())

    def clear(self) -> None:
        """Remove all sessions."""
        with self._lock:
            self._sessions.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)

    # ------------------------------------------------------------------ data

    def upload_dataset(
        self,
        session_id: str,
        name: str,
        df: pd.DataFrame,
    ) -> None:
        """Store *df* under *name* in the given session.

        Raises
        ------
        KeyError
            If *session_id* does not exist.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(f"Session not found: {session_id}")
            session.datasets[name] = df

    def get_datasets(self, session_id: str) -> Dict[str, pd.DataFrame]:
        """Return a shallow copy of the session's dataset dict.

        Raises
        ------
        KeyError
            If *session_id* does not exist.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(f"Session not found: {session_id}")
            return dict(session.datasets)

    # ------------------------------------------------------------------ messages

    def add_message(self, session_id: str, message: ChatMessage) -> None:
        """Append *message* to the session's history.

        Raises
        ------
        KeyError
            If *session_id* does not exist.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(f"Session not found: {session_id}")
            session.messages.append(message)

    def get_history(self, session_id: str) -> List[ChatMessage]:
        """Return a copy of the message history.

        Raises
        ------
        KeyError
            If *session_id* does not exist.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(f"Session not found: {session_id}")
            return list(session.messages)


# ---------------------------------------------------------------------------
# MongoDB-backed session store
# ---------------------------------------------------------------------------


class MongoChatSessionStore:
    """MongoDB-backed persistent store for :class:`ChatSession` objects.

    Uses **pymongo** (sync driver).  For async FastAPI endpoints, wrap calls
    in ``asyncio.to_thread`` or switch to the ``motor`` async driver.

    Session documents are stored in a single ``chat_sessions`` collection.
    Messages are **embedded** inside the session document (optimal for
    chat — reads are always per-session and message counts stay bounded).

    DataFrames are **not** persisted to MongoDB.  They are held in a
    per-process ``_df_cache`` dict.  If the server restarts the user
    re-uploads — identical to ChatGPT / Claude behaviour.  Dataset *names*
    are tracked in MongoDB so the UI can show what was previously uploaded.

    Parameters
    ----------
    mongo_uri : str
        MongoDB connection string, e.g.
        ``"mongodb://localhost:27017"`` or an Atlas SRV URI.
    db_name : str
        Database name (default ``"ai_workspace"``).
    collection_name : str
        Collection name (default ``"chat_sessions"``).
    session_ttl_seconds : int | None
        When set, a TTL index on ``expires_at`` is created so MongoDB
        automatically removes stale sessions.  ``None`` disables TTL.
    _client : pymongo.MongoClient | None
        Inject a pre-built client (e.g. ``mongomock.MongoClient()`` for
        unit tests) instead of creating a real one from *mongo_uri*.

    Examples
    --------
    ::

        store = MongoChatSessionStore("mongodb://localhost:27017")
        session = store.create(metadata={"user_id": "u1"})
        store.upload_dataset(session.session_id, "sales", df)
        store.add_message(session.session_id, ChatMessage(role="user", content="hi"))
        history = store.get_history(session.session_id)

        # Unit-test with mongomock (no real MongoDB needed):
        import mongomock  # noqa: E402, F401
        store = MongoChatSessionStore("mongodb://localhost", _client=mongomock.MongoClient())
    """

    def __init__(
        self,
        mongo_uri: str = "mongodb://localhost:27017",
        db_name: str = "ai_workspace",
        collection_name: str = "chat_sessions",
        session_ttl_seconds: Optional[int] = None,
        _client=None,
    ) -> None:
        if _client is not None:
            self._client = _client
        else:
            import pymongo  # lazy import — only needed when this class is used  # noqa: E402, F401

            self._client = pymongo.MongoClient(mongo_uri)

        self._col = self._client[db_name][collection_name]
        self._session_ttl_seconds = session_ttl_seconds

        # In-memory DataFrame cache: {session_id: {name: DataFrame}}
        self._df_cache: Dict[str, Dict[str, pd.DataFrame]] = {}
        self._lock = threading.Lock()  # guards _df_cache only

        self._ensure_indexes()

    # ------------------------------------------------------------------ indexes

    def _ensure_indexes(self) -> None:
        """Create indexes if they don't already exist."""
        # TTL index for automatic session expiry
        if self._session_ttl_seconds is not None:
            self._col.create_index(
                "expires_at",
                expireAfterSeconds=0,  # MongoDB uses the datetime value itself
                background=True,
                name="ttl_expires_at",
            )

    # ------------------------------------------------------------------ internal helpers

    @staticmethod
    def _msg_to_doc(msg: ChatMessage) -> dict:
        return {
            "role": msg.role,
            "content": msg.content,
            "artifact": msg.artifact,
            "agent_used": msg.agent_used,
            "timestamp": msg.timestamp,
        }

    @staticmethod
    def _doc_to_msg(doc: dict) -> ChatMessage:
        return ChatMessage(
            role=doc["role"],
            content=doc["content"],
            artifact=doc.get("artifact"),
            agent_used=doc.get("agent_used"),
            timestamp=doc.get("timestamp", datetime.now(timezone.utc)),
        )

    def _doc_to_session(self, doc: dict) -> ChatSession:
        sid = doc["_id"]
        messages = [self._doc_to_msg(m) for m in doc.get("messages", [])]
        # Reattach any cached DataFrames
        with self._lock:
            datasets = dict(self._df_cache.get(sid, {}))
        return ChatSession(
            session_id=sid,
            messages=messages,
            datasets=datasets,
            created_at=doc.get("created_at", datetime.now(timezone.utc)),
            metadata=doc.get("metadata", {}),
        )

    def _expires_at(self) -> Optional[datetime]:
        if self._session_ttl_seconds is None:
            return None
        from datetime import timedelta  # noqa: E402, F401

        return datetime.now(timezone.utc) + timedelta(seconds=self._session_ttl_seconds)

    # ------------------------------------------------------------------ sessions

    def create(
        self,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ChatSession:
        """Create and persist a new session, then return it."""
        sid = session_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        doc = {
            "_id": sid,
            "metadata": metadata or {},
            "created_at": now,
            "expires_at": self._expires_at(),
            "dataset_names": [],
            "messages": [],
        }
        self._col.insert_one(doc)
        return ChatSession(session_id=sid, metadata=metadata or {}, created_at=now)

    def get(self, session_id: str) -> Optional[ChatSession]:
        """Return the session or *None* if not found."""
        doc = self._col.find_one({"_id": session_id})
        if doc is None:
            return None
        return self._doc_to_session(doc)

    def delete(self, session_id: str) -> bool:
        """Delete a session.  Returns *True* if it existed."""
        result = self._col.delete_one({"_id": session_id})
        with self._lock:
            self._df_cache.pop(session_id, None)
        return result.deleted_count > 0

    def list_ids(self) -> List[str]:
        """Return all active session ids."""
        return [doc["_id"] for doc in self._col.find({}, {"_id": 1})]

    def clear(self) -> None:
        """Remove all sessions (use with care)."""
        self._col.delete_many({})
        with self._lock:
            self._df_cache.clear()

    def __len__(self) -> int:
        return self._col.count_documents({})

    # ------------------------------------------------------------------ data

    def upload_dataset(
        self,
        session_id: str,
        name: str,
        df: pd.DataFrame,
    ) -> None:
        """Cache *df* in-memory and record its name in MongoDB.

        Raises
        ------
        KeyError
            If *session_id* does not exist.
        """
        if self._col.count_documents({"_id": session_id}) == 0:
            raise KeyError(f"Session not found: {session_id}")

        # Track name in MongoDB (for UI awareness even after server restart)
        self._col.update_one(
            {"_id": session_id},
            {"$addToSet": {"dataset_names": name}},
        )
        # Store actual DataFrame in-memory
        with self._lock:
            if session_id not in self._df_cache:
                self._df_cache[session_id] = {}
            self._df_cache[session_id][name] = df

    def get_datasets(self, session_id: str) -> Dict[str, pd.DataFrame]:
        """Return a shallow copy of the in-memory DataFrame cache for *session_id*.

        Raises
        ------
        KeyError
            If *session_id* does not exist.
        """
        if self._col.count_documents({"_id": session_id}) == 0:
            raise KeyError(f"Session not found: {session_id}")
        with self._lock:
            return dict(self._df_cache.get(session_id, {}))

    # ------------------------------------------------------------------ messages

    def add_message(self, session_id: str, message: ChatMessage) -> None:
        """Append *message* to the session document in MongoDB.

        Raises
        ------
        KeyError
            If *session_id* does not exist.
        """
        result = self._col.update_one(
            {"_id": session_id},
            {"$push": {"messages": self._msg_to_doc(message)}},
        )
        if result.matched_count == 0:
            raise KeyError(f"Session not found: {session_id}")

    def get_history(self, session_id: str) -> List[ChatMessage]:
        """Return the message history for *session_id*.

        Raises
        ------
        KeyError
            If *session_id* does not exist.
        """
        doc = self._col.find_one({"_id": session_id}, {"messages": 1})
        if doc is None:
            raise KeyError(f"Session not found: {session_id}")
        return [self._doc_to_msg(m) for m in doc.get("messages", [])]
