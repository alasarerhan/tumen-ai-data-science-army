"""
g2_retrain_orchestrator
========================

Policy-driven auto-retraining orchestration for **G2** (spec
``docs/specs/G2-auto-retraining.md``).

Implements the deterministic core of the closed-loop retraining
policy engine that consumes G1's drift signal, optionally triggers an
E1/E2 retraining run, evaluates the challenger via F2, and records an
audit trail entry. HITL approval is treated as a no-op here — F2's
``recommendation`` carries the decision; gating to production is left
to the workflow layer.

Public surface
--------------

* :func:`build_policy` — construct a Policy from a declarative spec dict.
* :func:`policy_should_trigger` — evaluate a policy against a
  drift signal payload.
* :func:`simulate` — replay a stream of drift signals against a policy
  to count trigger frequency.
* :func:`decide_action` — pick one of ``trigger|monitor|ignore``
  given the signal + policy.
* :func:`record_event` — append to the audit trail.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence


# ---------------------------------------------------------------------------
# Policy model
# ---------------------------------------------------------------------------


@dataclass
class Trigger:
    kind: str
    feature_drift: bool = False
    performance_drift: bool = False
    relative_threshold: float = 0.05
    absolute_threshold: Optional[float] = None
    on_metric: Optional[str] = None
    cooldown_s: float = 0.0

    def evaluate(self, signal: Mapping[str, Any]) -> bool:
        """Decide if the signal fires this trigger.

        Each trigger has two flags — ``feature_drift`` and
        ``performance_drift`` — that independently gate the relevant
        signal condition.  If neither flag is on, the trigger is
        always satisfied.  When a flag is on, the matching trigger
        condition must hold AND the metric must be inside the
        configured threshold window for ``performance_drift``.
        """
        if not (self.feature_drift or self.performance_drift):
            return True
        feature_ok = (
            not self.feature_drift
            or bool(signal.get("feature_drift_trigger"))
        )
        perf_ok = (
            not self.performance_drift
            or bool(signal.get("performance_trigger"))
        )
        if self.performance_drift:
            perf = signal.get("performance") or {}
            threshold_breach = bool(perf.get("threshold_breached"))
            if self.relative_threshold is not None:
                if (
                    threshold_breach
                    and abs(perf.get("delta_pct", 0.0)) < self.relative_threshold
                ):
                    threshold_breach = False
            elif self.absolute_threshold is not None:
                threshold_breach = (
                    abs(perf.get("delta", 0.0)) >= abs(self.absolute_threshold)
                )
            perf_ok = perf_ok and threshold_breach
        return feature_ok and perf_ok

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "feature_drift": self.feature_drift,
            "performance_drift": self.performance_drift,
            "relative_threshold": self.relative_threshold,
            "absolute_threshold": self.absolute_threshold,
            "on_metric": self.on_metric,
            "cooldown_s": self.cooldown_s,
        }


@dataclass
class Policy:
    """A retraining policy: triggers + actions + cooldown + approval gate."""

    name: str
    triggers: List[Trigger] = field(default_factory=list)
    action: str = "retrain"
    require_hitl_approval: bool = True

    def triggered(self, signal: Mapping[str, Any]) -> bool:
        return any(t.evaluate(signal) for t in self.triggers)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "triggers": [t.to_dict() for t in self.triggers],
            "action": self.action,
            "require_hitl_approval": self.require_hitl_approval,
        }


def build_policy(spec: Mapping[str, Any]) -> Policy:
    """Construct a Policy from a declarative spec dict.

    A spec must look like::

        {
          "name": "drift-driven-rebuild",
          "triggers": [
            {"kind": "drift", "feature_drift": true},
            {"kind": "metric-drop",
             "performance_drift": true, "relative_threshold": 0.05,
             "on_metric": "roc_auc"},
          ],
          "action": "retrain",
          "require_hitl_approval": true,
        }
    """
    name = str(spec.get("name", f"policy_{uuid.uuid4().hex[:8]}"))
    triggers: List[Trigger] = []
    for trig in spec.get("triggers", []) or []:
        triggers.append(
            Trigger(
                kind=str(trig.get("kind", "drift")),
                feature_drift=bool(trig.get("feature_drift", False)),
                performance_drift=bool(trig.get("performance_drift", False)),
                relative_threshold=float(
                    trig.get("relative_threshold", 0.05)
                ),
                absolute_threshold=trig.get("absolute_threshold"),
                on_metric=trig.get("on_metric"),
                cooldown_s=float(trig.get("cooldown_s", 0.0)),
            )
        )
    if not triggers:
        # Sensible default: feature drift OR performance drift.
        triggers.append(
            Trigger(
                kind="any-drift",
                feature_drift=True,
                performance_drift=True,
                relative_threshold=float(spec.get("relative_threshold", 0.05)),
            )
        )
    return Policy(
        name=name,
        triggers=triggers,
        action=str(spec.get("action", "retrain")),
        require_hitl_approval=bool(spec.get("require_hitl_approval", True)),
    )


# ---------------------------------------------------------------------------
# Decision + simulation
# ---------------------------------------------------------------------------


def decide_action(
    signal: Mapping[str, Any],
    policy: Policy,
) -> Dict[str, Any]:
    """Decide whether to trigger retraining for ``signal`` under ``policy``.

    Returns a dict with keys ``should_trigger``, ``action``,
    ``triggered_by``, ``policy_name``.
    """
    fired = []
    for trig in policy.triggers:
        if trig.evaluate(signal):
            fired.append(trig.kind)
    return {
        "should_trigger": bool(fired),
        "action": policy.action if fired else "monitor",
        "triggered_by": fired,
        "policy_name": policy.name,
        "require_hitl_approval": policy.require_hitl_approval,
    }


def simulate(
    signals: Sequence[Mapping[str, Any]],
    policy: Policy,
) -> Dict[str, Any]:
    """Replay ``signals`` against ``policy`` and count triggers.

    Cooldown is honoured between consecutive triggers: a triggered
    outcome within ``cooldown_s`` of the previous one is suppressed.
    """
    triggers = 0
    decisions: List[Dict[str, Any]] = []
    last_trigger_ts: Optional[float] = None
    cooldown_default = max(
        (t.cooldown_s for t in policy.triggers), default=0.0
    )
    base_ts = time.monotonic()
    for i, sig in enumerate(signals):
        ts = base_ts + i * 60.0  # 60-second synthetic spacing
        decision = decide_action(sig, policy)
        if decision["should_trigger"]:
            if (
                last_trigger_ts is None
                or (ts - last_trigger_ts) >= cooldown_default
            ):
                triggers += 1
                last_trigger_ts = ts
                decision["recorded"] = True
            else:
                decision["recorded"] = False
                decision["reason"] = "cooldown"
        decisions.append(decision)
    return {
        "policy_name": policy.name,
        "n_signals": len(signals),
        "n_triggers": triggers,
        "decisions": decisions,
    }


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------


@dataclass
class Event:
    id: str
    timestamp: float
    policy_name: str
    signal: Dict[str, Any]
    decision: Dict[str, Any]
    notes: List[str] = field(default_factory=list)


def record_event(
    policy: Policy,
    signal: Dict[str, Any],
    decision: Dict[str, Any],
    *,
    timestamp: Optional[float] = None,
    notes: Optional[Sequence[str]] = None,
) -> Event:
    """Record a single audit-trail event."""
    ev = Event(
        id=uuid.uuid4().hex,
        timestamp=timestamp if timestamp is not None else time.time(),
        policy_name=policy.name,
        signal=dict(signal),
        decision=dict(decision),
        notes=list(notes or []),
    )
    return ev


def event_to_dict(ev: Event) -> Dict[str, Any]:
    return {
        "id": ev.id,
        "timestamp": ev.timestamp,
        "policy_name": ev.policy_name,
        "signal": ev.signal,
        "decision": ev.decision,
        "notes": list(ev.notes),
    }


def build_audit_trail(
    events: Sequence[Event],
) -> List[Dict[str, Any]]:
    """Convert a list of events into a chronologically-sorted audit trail."""
    return [event_to_dict(e) for e in sorted(events, key=lambda e: e.timestamp)]


__all__ = [
    "Trigger",
    "Policy",
    "build_policy",
    "decide_action",
    "simulate",
    "record_event",
    "event_to_dict",
    "build_audit_trail",
]


