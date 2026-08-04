from __future__ import annotations

"""g7_alerting. Deterministic incident / alerting tools.
Implements G7 — define alert rules (threshold on a metric stream),
evaluate them against observations, route to channels (Slack,
email, webhook), support escalation chains (level-1 → level-2
after timeout), and acknowledge / resolve incidents.
"""

import time  # noqa: E402, F401
import uuid  # noqa: E402, F401
from dataclasses import dataclass, field  # noqa: E402, F401
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence  # noqa: E402, F401

VALID_SEVERITIES = {"info", "warning", "critical"}
VALID_COMPARATORS = {">", ">=", "<", "<=", "==", "!="}
VALID_CHANNELS = {"slack", "email", "webhook"}


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> float:
    return time.time()


# ----- Alert rules ---------------------------------------------------------


@dataclass
class AlertRule:
    rule_id: str
    name: str
    metric: str
    comparator: str
    threshold: float
    severity: str
    channels: List[str]
    description: str = ""


@dataclass
class AlertStore:
    rules: List[AlertRule] = field(default_factory=list)

    def add(self, r: AlertRule) -> None:
        self.rules.append(r)

    def by_id(self, rule_id: str) -> Optional[AlertRule]:
        return next((r for r in self.rules if r.rule_id == rule_id), None)


def define_rule(
    store: AlertStore,
    *,
    name: str,
    metric: str,
    comparator: str,
    threshold: float,
    severity: str,
    channels: Sequence[str],
    description: str = "",
    rule_id: Optional[str] = None,
) -> AlertRule:
    if comparator not in VALID_COMPARATORS:
        raise ValueError(f"comparator must be one of {sorted(VALID_COMPARATORS)}")
    if severity not in VALID_SEVERITIES:
        raise ValueError(f"severity must be one of {sorted(VALID_SEVERITIES)}")
    for ch in channels:
        if ch not in VALID_CHANNELS:
            raise ValueError(f"channel {ch!r} not in {sorted(VALID_CHANNELS)}")
    rule = AlertRule(
        rule_id=rule_id or _new_id(),
        name=name,
        metric=metric,
        comparator=comparator,
        threshold=float(threshold),
        severity=severity,
        channels=list(channels),
        description=description,
    )
    store.add(rule)
    return rule


def _compare(value: float, comparator: str, threshold: float) -> bool:
    if comparator == ">":
        return value > threshold
    if comparator == ">=":
        return value >= threshold
    if comparator == "<":
        return value < threshold
    if comparator == "<=":
        return value <= threshold
    if comparator == "==":
        return value == threshold
    if comparator == "!=":
        return value != threshold
    raise ValueError(f"unknown comparator: {comparator}")


def evaluate_rule(
    rule: AlertRule,
    *,
    metric_value: float,
) -> bool:
    return _compare(float(metric_value), rule.comparator, rule.threshold)


# ----- Incidents -----------------------------------------------------------


@dataclass
class EscalationStep:
    level: int
    channel: str
    timeout_seconds: float
    triggered: bool = False
    triggered_at: Optional[float] = None


@dataclass
class Incident:
    incident_id: str
    rule_id: str
    severity: str
    metric: str
    value: float
    threshold: float
    comparator: str
    channels_notified: List[str]
    status: str  # "open" | "acknowledged" | "resolved"
    escalation: List[EscalationStep]
    raised_at: float
    acknowledged_at: Optional[float] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[float] = None
    resolution_note: str = ""


def raise_incident(
    store: AlertStore,
    *,
    rule_id: str,
    metric_value: float,
    escalation_policy: Optional[Sequence[Mapping[str, Any]]] = None,
    incident_id: Optional[str] = None,
) -> Incident:
    rule = store.by_id(rule_id)
    if rule is None:
        raise KeyError(f"rule_id not found: {rule_id}")
    if not evaluate_rule(rule, metric_value=metric_value):
        raise ValueError("rule not triggered; metric_value does not violate threshold")
    esc_steps = [
        EscalationStep(
            level=int(s["level"]),
            channel=str(s["channel"]),
            timeout_seconds=float(s.get("timeout_seconds", 300.0)),
        )
        for s in (escalation_policy or [])
    ]
    inc = Incident(
        incident_id=incident_id or _new_id(),
        rule_id=rule_id,
        severity=rule.severity,
        metric=rule.metric,
        value=float(metric_value),
        threshold=rule.threshold,
        comparator=rule.comparator,
        channels_notified=list(rule.channels),
        status="open",
        escalation=esc_steps,
        raised_at=_now(),
    )
    return inc


def acknowledge_incident(
    inc: Incident,
    *,
    by: str,
    note: str = "",
) -> None:
    if inc.status not in ("open", "acknowledged"):
        raise ValueError(f"cannot acknowledge incident in status {inc.status!r}")
    if inc.status == "open":
        inc.acknowledged_at = _now()
        inc.acknowledged_by = by
    inc.status = "acknowledged"
    if note:
        existing = inc.resolution_note
        sep = "\n" if existing else ""
        inc.resolution_note = f"{existing}{sep}ack@{by}: {note}"


def resolve_incident(
    inc: Incident,
    *,
    note: str = "",
) -> None:
    if inc.status == "resolved":
        return
    inc.status = "resolved"
    inc.resolved_at = _now()
    if note:
        existing = inc.resolution_note
        sep = "\n" if existing else ""
        inc.resolution_note = f"{existing}{sep}resolved: {note}"


# ----- Escalation ticks ---------------------------------------------------


def tick_escalation(
    inc: Incident,
    *,
    now: Optional[float] = None,
) -> List[EscalationStep]:
    """Walk the escalation chain. Trigger any step whose
    timeout has elapsed since the previous trigger / raised_at.
    Returns the list of newly-triggered steps (not yet
    notified to the channel)."""
    if inc.status == "resolved":
        return []
    ts = now if now is not None else _now()
    last_ts = inc.raised_at
    triggered: List[EscalationStep] = []
    for step in inc.escalation:
        if step.triggered:
            last_ts = step.triggered_at or last_ts
            continue
        if ts - last_ts >= step.timeout_seconds:
            step.triggered = True
            step.triggered_at = ts
            triggered.append(step)
            last_ts = ts
    return triggered


# ----- Channel routing ----------------------------------------------------


def route_to_channels(
    inc: Incident,
    *,
    send_fn: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """Build a payload per channel. If send_fn is provided, also
    invoke it. Returns a routing summary."""
    base_payload = {
        "incident_id": inc.incident_id,
        "rule_id": inc.rule_id,
        "severity": inc.severity,
        "metric": inc.metric,
        "value": inc.value,
        "threshold": inc.threshold,
        "comparator": inc.comparator,
        "status": inc.status,
        "raised_at": inc.raised_at,
    }
    sent: Dict[str, Any] = {}
    for ch in inc.channels_notified:
        sent[ch] = {"payload": base_payload, "delivered": False}
        if send_fn is not None:
            try:
                send_fn(ch, base_payload)
                sent[ch]["delivered"] = True
            except Exception as exc:
                sent[ch]["error"] = str(exc)
    return {
        "incident_id": inc.incident_id,
        "channels": sent,
    }


def channel_template(channel: str, payload: Mapping[str, Any]) -> str:
    """Render a human-readable message for a given channel."""
    if channel == "slack":
        return (
            f":rotating_light: *[{payload['severity']}]* "
            f"{payload['metric']}={payload['value']} "
            f"{payload['comparator']} {payload['threshold']} "
            f"(incident {payload['incident_id']})"
        )
    if channel == "email":
        return (
            f"Subject: [{payload['severity'].upper()}] "
            f"{payload['metric']} incident\n\n"
            f"Incident {payload['incident_id']}\n"
            f"Metric: {payload['metric']}={payload['value']} "
            f"{payload['comparator']} {payload['threshold']}\n"
            f"Status: {payload['status']}\n"
        )
    if channel == "webhook":
        return (
            f'{{"incident_id":"{payload["incident_id"]}",'
            f'"severity":"{payload["severity"]}",'
            f'"metric":"{payload["metric"]}",'
            f'"value":{payload["value"]}}}'
        )
    raise ValueError(f"unknown channel: {channel}")


# ----- Aggregation --------------------------------------------------------


@dataclass
class IncidentStore:
    incidents: List[Incident] = field(default_factory=list)

    def add(self, inc: Incident) -> None:
        self.incidents.append(inc)

    def filter(
        self,
        *,
        status: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> List[Incident]:
        out = list(self.incidents)
        if status is not None:
            out = [i for i in out if i.status == status]
        if severity is not None:
            out = [i for i in out if i.severity == severity]
        return out


def summarise(
    store: IncidentStore,
) -> Dict[str, int]:
    counts: Dict[str, int] = {
        "total": len(store.incidents),
        "open": 0,
        "acknowledged": 0,
        "resolved": 0,
        "info": 0,
        "warning": 0,
        "critical": 0,
    }
    for inc in store.incidents:
        counts[inc.status] = counts.get(inc.status, 0) + 1
        counts[inc.severity] = counts.get(inc.severity, 0) + 1
    return counts
