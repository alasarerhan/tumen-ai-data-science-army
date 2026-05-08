"""ContextStore — per-session runtime context for pipeline execution (M22).

Keeps data alive across pipeline steps so downstream agents can access
datasets, intermediate results, and configuration without re-loading from disk.

Design
------
* **Thread-safe**: a single ``threading.Lock`` guards all mutations.
* **In-memory**: suitable for interactive and short-lived sessions.
  For persistent or distributed deployments, replace the in-memory dict
  with a Redis or database-backed implementation while keeping the same
  public interface.
* **Two layers per session**:
  - Key/value store: arbitrary typed values (DataFrames, dicts, strings…)
  - Artifact log: ordered list of step outputs with provenance metadata

Usage
-----
::

    from ai_data_science_team.context_store import ContextStore

    store = ContextStore()
    sid = store.create_session(user_id="u1", workspace_id="ws1")

    # Store the loaded dataset
    store.set(sid, "raw_df", df)

    # Retrieve it in a downstream step
    df = store.get(sid, "raw_df")

    # Record a step artifact
    store.append_artifact(sid, "chart", chart_spec, step_id="viz", agent_name="DataVizAgent")

    # Get all artifacts produced so far
    artifacts = store.get_artifacts(sid)
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ContextStore:
    """Thread-safe, in-memory per-session context store.

    Attributes (per session)
    ------------------------
    _meta     : dict  — session creation metadata (ids, timestamps).
    _artifacts: list  — ordered list of step artifact records.
    + any user-defined key/value pairs set via :meth:`set`.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------ sessions

    def create_session(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        scenario: str = "supervised",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new session and return its id.

        Parameters
        ----------
        session_id : str | None
            Explicit id to use; an UUID4 is generated when None.
        user_id : str | None
            Platform user id.
        workspace_id : str | None
            Platform workspace id.
        scenario : str
            Execution scenario (``"dynamic"`` / ``"supervised"`` / ``"manual"``).
        metadata : dict | None
            Additional key/value pairs stored in ``_meta``.
        """
        sid = session_id or str(uuid.uuid4())
        with self._lock:
            self._sessions[sid] = {
                "_meta": {
                    "session_id": sid,
                    "user_id": user_id,
                    "workspace_id": workspace_id,
                    "scenario": scenario,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    **(metadata or {}),
                },
                "_artifacts": [],
            }
        return sid

    def session_exists(self, session_id: str) -> bool:
        """Return True if *session_id* is a known session."""
        with self._lock:
            return session_id in self._sessions

    def get_session(self, session_id: str) -> Dict[str, Any]:
        """Return a *shallow copy* of the full session context dict.

        Raises
        ------
        KeyError
            If *session_id* does not exist.
        """
        with self._lock:
            if session_id not in self._sessions:
                raise KeyError(f"Session '{session_id}' does not exist.")
            return dict(self._sessions[session_id])

    def get_meta(self, session_id: str) -> Dict[str, Any]:
        """Return a copy of the session metadata dict."""
        with self._lock:
            session = self._sessions.get(session_id, {})
            return dict(session.get("_meta", {}))

    def update_meta(self, session_id: str, **kwargs: Any) -> None:
        """Update session metadata fields in place."""
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].setdefault("_meta", {}).update(kwargs)

    def clear_session(self, session_id: str) -> None:
        """Delete a session and all its data."""
        with self._lock:
            self._sessions.pop(session_id, None)

    def list_sessions(self) -> List[str]:
        """Return a list of all active session ids."""
        with self._lock:
            return list(self._sessions.keys())

    # ------------------------------------------------------------------ key/value

    def set(self, session_id: str, key: str, value: Any) -> None:
        """Set an arbitrary key/value in the session context.

        Creates the session data dict if it does not exist yet (lenient mode).
        """
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = {"_meta": {}, "_artifacts": []}
            self._sessions[session_id][key] = value

    def get(self, session_id: str, key: str, default: Any = None) -> Any:
        """Get a value by key; returns *default* if key or session not found."""
        with self._lock:
            return self._sessions.get(session_id, {}).get(key, default)

    def delete(self, session_id: str, key: str) -> None:
        """Remove a key from the session context.  Silent if key not found."""
        with self._lock:
            self._sessions.get(session_id, {}).pop(key, None)

    def keys(self, session_id: str) -> List[str]:
        """Return all user-defined keys in the session (excludes _meta, _artifacts)."""
        with self._lock:
            return [
                k
                for k in self._sessions.get(session_id, {}).keys()
                if not k.startswith("_")
            ]

    # ------------------------------------------------------------------ artifacts

    def append_artifact(
        self,
        session_id: str,
        artifact_type: str,
        content: Any,
        step_id: Optional[str] = None,
        agent_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Append a step output artifact to the session's artifact log.

        Parameters
        ----------
        artifact_type : str
            Descriptor such as ``"dataframe"``, ``"chart"``, ``"report"``,
            ``"model"``, ``"metrics"``.
        content : Any
            The artifact payload (DataFrame, dict, string, bytes, etc.).
        step_id : str | None
            The WorkflowSpec step id that produced this artifact.
        agent_name : str | None
            The agent that produced this artifact.

        Returns
        -------
        dict
            The artifact record that was appended.
        """
        record: Dict[str, Any] = {
            "artifact_type": artifact_type,
            "content": content,
            "step_id": step_id,
            "agent_name": agent_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = {"_meta": {}, "_artifacts": []}
            self._sessions[session_id]["_artifacts"].append(record)
        return record

    def get_artifacts(
        self,
        session_id: str,
        artifact_type: Optional[str] = None,
        step_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return the artifact log, optionally filtered.

        Parameters
        ----------
        artifact_type : str | None
            Filter to artifacts of this type.
        step_id : str | None
            Filter to artifacts produced by this step.
        """
        with self._lock:
            records = list(self._sessions.get(session_id, {}).get("_artifacts", []))

        if artifact_type:
            records = [r for r in records if r.get("artifact_type") == artifact_type]
        if step_id:
            records = [r for r in records if r.get("step_id") == step_id]

        return records

    def artifact_count(self, session_id: str) -> int:
        """Return the number of artifacts in the session."""
        with self._lock:
            return len(self._sessions.get(session_id, {}).get("_artifacts", []))


__all__ = ["ContextStore"]
