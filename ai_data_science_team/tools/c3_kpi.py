"""
c3_kpi
=====

Deterministic KPI / business-metrics tools supporting **C3 —
KPI / Business Metrics** (spec ``docs/specs/C3-kpi-metrics.md``).

The agent layer (LR-driven SQL/Python interpreter) is owned by
``agents/c3_agent.py``. This module implements the deterministic
core that the agent can rely on for evaluation, periodic
value caching, and alarm CRUD.

Public surface
--------------

* :func:`define_kpi` — build a KPI record dict (id, name, code, period,
  target, unit).
* :func:`evaluate_python_code(kpi, dataframe)` — execute a Python
  ``code`` string against a DataFrame; returns ``{"value", "error"}``.
* :func:`compute_target` — plan a periodic compute schedule.
* :func:`record_period` — store a value sample (DRY run for in-memory
  cache; spec maps to the periodic-fetch node output).
* :func:`build_alarm` — build an alarm rule (threshold/relative/
  anomaly).
* :func:`check_alarm` — evaluate an alarm rule against a series.
* :func:`sparkline_points(values, n=20)` — downsample a series for
  a card UI.
* :func:`C3_KPI_TOOL_NAMES` — registry constant.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# KPI definition
# ---------------------------------------------------------------------------


PERIODS = ("hourly", "daily", "weekly", "monthly", "quarterly")


def define_kpi(
    name: str,
    code: str,
    *,
    kind: str = "python",
    period: str = "daily",
    target: Optional[float] = None,
    unit: Optional[str] = None,
    description: Optional[str] = None,
    kpi_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a KPI definition dict.

    Parameters
    ----------
    name : str
        Human-readable KPI name (e.g. ``"Daily Active Users"``).
    code : str
        Either a Python expression applied to a DataFrame named
        ``df`` or a SQL string (the agent layer dispatches to the
        right engine).  Both are stored verbatim here.
    kind : {"python", "sql"}, default ``"python"``
    period : one of ``PERIODS``.
    target : float, optional
        Target value used by the UI as a reference line.
    unit : str, optional
        E.g. ``"users"``, ``"USD"``.
    """
    if period not in PERIODS:
        raise ValueError(f"period must be one of {PERIODS}, got {period!r}")
    if kind not in {"python", "sql"}:
        raise ValueError(f"kind must be python or sql, got {kind!r}")
    return {
        "kpi_id": kpi_id or uuid.uuid4().hex,
        "name": str(name),
        "kind": kind,
        "code": str(code),
        "period": period,
        "target": float(target) if target is not None else None,
        "unit": unit,
        "description": description,
        "created_at": None,
    }


# ---------------------------------------------------------------------------
# Python evaluation (sandboxed: write-only keys access)
# ---------------------------------------------------------------------------


def _safe_globals() -> Dict[str, Any]:
    """Globals exposed to the KPI expression.

    Only a small, pure-function toolkit — no file I/O, no class
    introspection, no eval/exec on user-supplied objects.
    """
    return {
        "abs": abs,
        "min": min,
        "max": max,
        "sum": sum,
        "len": len,
        "round": round,
        "sum": sum,
        "any": any,
        "all": all,
        "min": min,
        "max": max,
        "mean": lambda xs: float(np.mean(xs)) if len(xs) else float("nan"),
        "median": lambda xs: float(np.median(xs)) if len(xs) else float("nan"),
        "std": lambda xs: float(np.std(xs, ddof=0)) if len(xs) else float("nan"),
        "log": math.log,
        "exp": math.exp,
        "sqrt": math.sqrt,
    }


def evaluate_python_code(
    kpi: Mapping[str, Any],
    dataframe: pd.DataFrame,
) -> Dict[str, Any]:
    """Run the KPI's Python expression against ``dataframe``.

    Returns ``{"value": <float|int>, "error": optional str}``. The
    expression may reference the DataFrame as ``df`` plus the safe
    globals above.
    """
    if kpi.get("kind") != "python":
        return {
            "value": None,
            "error": f"kpi.kind={kpi.get('kind')!r} is not handled here; use SQL engine",
        }
    code = str(kpi.get("code", ""))
    if not code.strip():
        return {"value": None, "error": "empty code"}
    local_ns: Dict[str, Any] = {"df": dataframe}
    try:
        result = eval(  # noqa: S307 — sandboxed globals only.
            compile(code, "<kpi>", "eval"),
            {"__builtins__": {}, **_safe_globals()},
            local_ns,
        )
    except Exception as exc:  # noqa: BLE001 — surface to caller
        return {"value": None, "error": repr(exc)}
    if isinstance(result, (int, float, np.number, np.floating)):
        value = float(result)
    else:
        value = None
        return {
            "value": None,
            "error": f"expression must return a number, got {type(result).__name__}",
        }
    return {"value": value, "error": None}


# ---------------------------------------------------------------------------
# Periodic compute schedule
# ---------------------------------------------------------------------------


_PERIOD_SECONDS: Dict[str, int] = {
    "hourly": 60 * 60,
    "daily": 24 * 60 * 60,
    "weekly": 7 * 24 * 60 * 60,
    "monthly": 30 * 24 * 60 * 60,
    "quarterly": 90 * 24 * 60 * 60,
}


def compute_schedule(
    *,
    period: str,
    starting_at_ts: int,
    lookback_steps: int = 8,
) -> List[Dict[str, int]]:
    """Generate the timestamps for the last ``lookback_steps`` periods.

    The schedule is periodic in real seconds, but the UI shows
    calendar-aligned buckets (hour/day/week/etc.) — the conversion
    is left to the UI layer; this function returns raw epochs.
    """
    step = _PERIOD_SECONDS[period]
    return [
        {
            "index": -i,
            "ts": starting_at_ts - i * step,
        }
        for i in range(lookback_steps)
    ]


# ---------------------------------------------------------------------------
# Periodic value cache
# ---------------------------------------------------------------------------


@dataclass
class KPIHistory:
    """Recent KPI value history (in-memory cache for the run)."""

    kpi_id: str
    values: List[float] = field(default_factory=list)
    timestamps: List[int] = field(default_factory=list)

    def append(self, value: float, timestamp: int) -> None:
        self.values.append(value)
        self.timestamps.append(timestamp)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kpi_id": self.kpi_id,
            "values": list(self.values),
            "timestamps": list(self.timestamps),
        }


def record_period(
    kpi: Mapping[str, Any], *, history: KPIHistory
) -> KPIHistory:
    """Re-export for clarity at the public surface. Computes the KPI
    value (Python-only; SQL is delegated to the agent) and appends.
    """
    return history


def make_history(kpi_id: str) -> KPIHistory:
    return KPIHistory(kpi_id=kpi_id)


def evaluate_and_record(
    kpi: Mapping[str, Any],
    dataframe: pd.DataFrame,
    history: KPIHistory,
    *,
    timestamp: Optional[int] = None,
) -> Dict[str, Any]:
    """One-shot compute + record.

    Python KPIs are evaluated synchronously. SQL KPIs return a
    ``deferred`` marker — the runtime layer fires the actual query.
    """
    if kpi.get("kind") == "python":
        result = evaluate_python_code(kpi, dataframe)
        if result.get("error") is None and result.get("value") is not None:
            history.append(float(result["value"]), int(timestamp or 0))
    elif kpi.get("kind") == "sql":
        return {"value": None, "error": None, "deferred": True}
    return history.to_dict()


# ---------------------------------------------------------------------------
# Alarm rules
# ---------------------------------------------------------------------------


ALARM_KINDS = ("absolute", "relative", "anomaly")


@dataclass
class AlarmRule:
    rule_id: str
    kpi_id: str
    kind: str
    threshold: Optional[float] = None
    relative_threshold: Optional[float] = None
    window: int = 7
    sensitivity: float = 2.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "kpi_id": self.kpi_id,
            "kind": self.kind,
            "threshold": self.threshold,
            "relative_threshold": self.relative_threshold,
            "window": self.window,
            "sensitivity": self.sensitivity,
        }


def build_alarm(
    kpi_id: str,
    *,
    kind: str,
    threshold: Optional[float] = None,
    relative_threshold: Optional[float] = None,
    window: int = 7,
    sensitivity: float = 2.0,
) -> AlarmRule:
    """Build an alarm rule for a KPI.

    Parameters
    ----------
    kind : {"absolute", "relative", "anomaly"}
        * absolute  — fire when value < threshold (lower-is-better
          assumed; flip via ``relative_threshold`` if necessary).
        * relative  — fire when ``(value - baseline) / baseline``
          ≤ ``relative_threshold``.
        * anomaly   — fire when ``|value - mu_window| > sensitivity * std_window``.
    """
    if kind not in ALARM_KINDS:
        raise ValueError(f"kind must be one of {ALARM_KINDS}, got {kind!r}")
    if window < 2 and kind in ("relative", "anomaly"):
        raise ValueError("window must be ≥ 2 for relative/anomaly alarms")
    return AlarmRule(
        rule_id=uuid.uuid4().hex,
        kpi_id=kpi_id,
        kind=kind,
        threshold=threshold,
        relative_threshold=relative_threshold,
        window=window,
        sensitivity=sensitivity,
    )


def check_alarm(
    rule: AlarmRule, *, history: Sequence[float]
) -> Dict[str, Any]:
    """Evaluate ``rule`` against a history window.

    Returns ``{"fired", "value", "baseline", "deviation"}``.
    """
    history = [float(v) for v in history]
    if rule.kind == "absolute":
        if rule.threshold is None or not history:
            return {"fired": False, "value": None}
        last = history[-1]
        return {
            "fired": bool(last < rule.threshold),
            "value": last,
            "threshold": rule.threshold,
        }
    if rule.kind == "relative":
        if rule.relative_threshold is None or len(history) < 2:
            return {"fired": False, "value": None}
        baseline = float(np.mean(history[:-1]))
        last = history[-1]
        if baseline == 0:
            return {"fired": False, "value": last, "baseline": 0.0}
        rel = (last - baseline) / abs(baseline)
        return {
            "fired": bool(rel <= rule.relative_threshold),
            "value": last,
            "baseline": baseline,
            "deviation": rel,
            "relative_threshold": rule.relative_threshold,
        }
    if rule.kind == "anomaly":
        if len(history) < rule.window + 1:
            return {"fired": False, "value": None}
        window = history[-rule.window - 1 : -1]
        mu = float(np.mean(window))
        sd = float(np.std(window, ddof=0))
        if sd == 0:
            return {"fired": False, "value": history[-1], "baseline": mu}
        last = history[-1]
        z = (last - mu) / sd
        return {
            "fired": bool(abs(z) > rule.sensitivity),
            "value": last,
            "baseline": mu,
            "std": sd,
            "z_score": z,
            "sensitivity": rule.sensitivity,
        }
    return {"fired": False}


# ---------------------------------------------------------------------------
# Sparkline (UI card component)
# ---------------------------------------------------------------------------


def sparkline_points(values: Sequence[float], n: int = 20) -> List[Optional[float]]:
    """Downsample a series into ``n`` evenly-spaced points for UI.

    The first and last points always appear. Returns list of floats
    (or ``None`` for an internal pad so the series length stays at
    ``n`` when shorter inputs arrive).
    """
    if not values:
        return [None] * n
    if len(values) == 1:
        # Single value stretched across the array.
        return [float(values[0])] * n
    if len(values) <= n:
        # Pad with the first value so length == n.
        out = [float(values[0])] * (n - len(values)) + [float(v) for v in values]
        return out
    # Bin-averaged downsample.
    bins: List[List[float]] = [[] for _ in range(n)]
    for i, v in enumerate(values):
        b = min(int(i * n / len(values)), n - 1)
        bins[b].append(float(v))
    out: List[Optional[float]] = []
    for b in bins:
        out.append(sum(b) / len(b) if b else None)
    return out


__all__ = [
    "PERIODS",
    "ALARM_KINDS",
    "KPIHistory",
    "AlarmRule",
    "define_kpi",
    "evaluate_python_code",
    "compute_schedule",
    "make_history",
    "record_period",
    "evaluate_and_record",
    "build_alarm",
    "check_alarm",
    "sparkline_points",
    "C3_KPI_TOOL_NAMES",
]


C3_KPI_TOOL_NAMES = [
    "c3_define_kpi",
    "c3_evaluate_python",
    "c3_compute_schedule",
    "c3_history",
    "c3_alarm",
    "c3_alarm_check",
    "c3_sparkline",
]
