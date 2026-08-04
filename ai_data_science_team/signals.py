from __future__ import annotations

"""WorkflowSignal — non-blocking, optional user intervention channel (M22).

Design philosophy
-----------------
Pipelines NEVER block waiting for a human. ``WorkflowSignal`` is the
mechanism through which users who *want* to intervene can do so at any
point during a run. The ``RuntimeEngine`` polls the ``SignalStore`` before
and after each step; if no signals are pending the run continues
uninterrupted.

The system notifies users (via platform notifications) only when *all*
automatic recovery options (retry + back-off, fallback chain, circuit
breaker) have been exhausted — not before.

Typical usage
-------------
::

    from ai_data_science_team.signals import SignalStore, WorkflowSignal, SignalType  # noqa: E402, F401

    store = SignalStore()

    # User emits a skip signal while the pipeline is running
    store.emit(WorkflowSignal(
        type=SignalType.SKIP,
        session_id="session-42",
        step_id="feature_engineering",
    ))

    # RuntimeEngine polls before executing each step
    pending = store.pop_pending("session-42")
    for signal in pending:
        # handle appropriately
        ...
"""

import threading  # noqa: E402, F401
import uuid  # noqa: E402, F401
from dataclasses import dataclass, field  # noqa: E402, F401
from datetime import datetime, timezone  # noqa: E402, F401
from enum import Enum  # noqa: E402, F401
from typing import Any, Dict, List, Optional  # noqa: E402, F401

DEFAULT_MAX_SIGNALS_PER_SESSION = 1000
MAX_SESSION_ID_LENGTH = 200


class SignalLimitExceededError(Exception):
    """Raised when a session has reached its maximum signal limit."""

    pass


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class SignalType(str, Enum):
    """Types of user-emitted workflow intervention signals."""

    PAUSE = "pause"  # Request a graceful pause after the current step
    RESUME = "resume"  # Resume after an engine-initiated pause
    SKIP = "skip"  # Skip a specific named step
    MODIFY = "modify"  # Override a step's instruction via payload
    ANNOTATE = "annotate"  # Attach a user note (non-functional, purely metadata)
    CANCEL = "cancel"  # Abort the entire workflow immediately


# ---------------------------------------------------------------------------
# Signal dataclass
# ---------------------------------------------------------------------------


@dataclass
class WorkflowSignal:
    """An intervention event emitted by a user or the system.

    Parameters
    ----------
    type : SignalType
        The kind of intervention.
    session_id : str
        The active session this signal targets.
    step_id : str | None
        Optional target step id (used by SKIP / MODIFY signals).
    payload : dict
        Arbitrary signal-specific data.  For MODIFY: ``{"instruction": ...}``.
        For ANNOTATE: ``{"note": ...}``.
    signal_id : str
        Auto-generated UUID for deduplication.
    timestamp : str
        UTC ISO-8601 creation time.
    consumed : bool
        Set to True by the SignalStore after the RuntimeEngine has processed
        this signal.
    """

    type: SignalType
    session_id: str
    step_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    consumed: bool = False

    def consume(self) -> "WorkflowSignal":
        """Mark this signal as consumed and return self (fluent API)."""
        self.consumed = True
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "type": self.type.value,
            "session_id": self.session_id,
            "step_id": self.step_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "consumed": self.consumed,
        }


# ---------------------------------------------------------------------------
# SignalStore
# ---------------------------------------------------------------------------


class SignalStore:
    """Thread-safe in-memory store for ``WorkflowSignal`` events per session.

    The ``RuntimeEngine`` calls :meth:`pop_pending` before/after each step
    to retrieve and act on any signals the user emitted while the pipeline
    was running.  Between polls the signals are buffered here.

    This class is intentionally simple (in-memory list per session).  For
    production use, replace with a Redis-backed implementation while keeping
    the same interface.

    Parameters
    ----------
    max_signals_per_session : int
        Maximum number of signals to store per session. Older signals are
        discarded when limit is reached. Default: 1000.
    """

    def __init__(self, max_signals_per_session: int = DEFAULT_MAX_SIGNALS_PER_SESSION) -> None:
        if max_signals_per_session < 1:
            raise ValueError(
                f"max_signals_per_session must be at least 1, got {max_signals_per_session}"
            )
        self._max_signals = max_signals_per_session
        self._lock = threading.Lock()
        self._signals: Dict[str, List[WorkflowSignal]] = {}

    # ------------------------------------------------------------------

    def emit(self, signal: WorkflowSignal) -> WorkflowSignal:
        """Add a signal to the session queue and return it.

        Raises
        ------
        ValueError
            If session_id is empty or too long.
        SignalLimitExceededError
            If the session has reached max_signals_per_session.
        """
        if not signal.session_id or not signal.session_id.strip():
            raise ValueError("session_id cannot be empty")
        if len(signal.session_id) > MAX_SESSION_ID_LENGTH:
            raise ValueError(
                f"session_id too long: {len(signal.session_id)} chars, "
                f"max is {MAX_SESSION_ID_LENGTH}"
            )

        with self._lock:
            session_signals = self._signals.setdefault(signal.session_id, [])
            if len(session_signals) >= self._max_signals:
                # Make room by dropping the oldest unconsumed signal (FIFO).
                # If all stored signals are already consumed, raise; otherwise
                # always reclaim exactly one slot so the new emit is accepted.
                for i, existing in enumerate(session_signals):
                    if not existing.consumed:
                        del session_signals[i]
                        break
                else:
                    raise SignalLimitExceededError(
                        f"Session {signal.session_id} has reached max signals limit "
                        f"({self._max_signals}). Clear consumed signals or increase limit."
                    )
            session_signals.append(signal)
        return signal

    def pop_pending(self, session_id: str) -> List[WorkflowSignal]:
        """Return *and consume* all non-consumed signals for a session.

        After this call, those signals have ``consumed=True`` and will not
        be returned again by subsequent calls.
        """
        with self._lock:
            signals = self._signals.get(session_id, [])
            pending = [s for s in signals if not s.consumed]
            for s in pending:
                s.consumed = True
        return pending

    def list_all(self, session_id: str) -> List[WorkflowSignal]:
        """Return all signals (including already consumed) for a session."""
        with self._lock:
            return list(self._signals.get(session_id, []))

    def clear(self, session_id: str) -> None:
        """Remove all signals for a session."""
        with self._lock:
            self._signals.pop(session_id, None)

    def session_ids(self) -> List[str]:
        """Return all session ids that have at least one signal."""
        with self._lock:
            return list(self._signals.keys())

    def cleanup_consumed(self, session_id: Optional[str] = None) -> int:
        """Remove consumed signals to free up space.

        Parameters
        ----------
        session_id : str | None
            If provided, only cleanup signals for this session.
            If None, cleanup all sessions.

        Returns
        -------
        int
            Number of consumed signals removed.
        """
        with self._lock:
            removed = 0
            if session_id:
                if session_id in self._signals:
                    before = len(self._signals[session_id])
                    self._signals[session_id] = [
                        s for s in self._signals[session_id] if not s.consumed
                    ]
                    removed = before - len(self._signals[session_id])
                    if not self._signals[session_id]:
                        del self._signals[session_id]
            else:
                for sid in list(self._signals.keys()):
                    before = len(self._signals[sid])
                    self._signals[sid] = [s for s in self._signals[sid] if not s.consumed]
                    removed += before - len(self._signals[sid])
                    if not self._signals[sid]:
                        del self._signals[sid]
            return removed

    def stats(self) -> Dict[str, Any]:
        """Return statistics about the signal store."""
        with self._lock:
            total_sessions = len(self._signals)
            total_signals = sum(len(s) for s in self._signals.values())
            consumed_signals = sum(
                sum(1 for s in signals if s.consumed) for signals in self._signals.values()
            )
            return {
                "total_sessions": total_sessions,
                "total_signals": total_signals,
                "consumed_signals": consumed_signals,
                "pending_signals": total_signals - consumed_signals,
                "max_signals_per_session": self._max_signals,
            }


# ---------------------------------------------------------------------------
# Global default store
# ---------------------------------------------------------------------------

_default_signal_store: Optional[SignalStore] = None
_store_lock = threading.Lock()


def get_signal_store() -> SignalStore:
    """Return the global default :class:`SignalStore` singleton."""
    global _default_signal_store
    if _default_signal_store is None:
        with _store_lock:
            if _default_signal_store is None:
                _default_signal_store = SignalStore()
    return _default_signal_store


def reset_signal_store() -> None:
    """Reset the global signal store singleton.

    WARNING: This function is for TESTING ONLY. Do not use in production.

    This function clears the global signal store singleton, allowing tests
    to start with a fresh state. Using this in production could cause
    race conditions and lost signals.

    Usage in tests:
        @pytest.fixture(autouse=True)
        def reset_stores():
            from ai_data_science_team.signals import reset_signal_store  # noqa: E402, F401
            reset_signal_store()
            yield
            reset_signal_store()
    """
    global _default_signal_store
    with _store_lock:
        if _default_signal_store is not None:
            _default_signal_store._signals.clear()
        _default_signal_store = None


__all__ = [
    "SignalType",
    "WorkflowSignal",
    "SignalStore",
    "SignalLimitExceededError",
    "get_signal_store",
    "reset_signal_store",
    "DEFAULT_MAX_SIGNALS_PER_SESSION",
    "MAX_SESSION_ID_LENGTH",
]
