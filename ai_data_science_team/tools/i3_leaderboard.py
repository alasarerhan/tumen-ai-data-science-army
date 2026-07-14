"""i3_leaderboard. Deterministic experiment-tracking / leaderboard
tools. Implements the I3 spec — record runs, query / rank /
filter, summarise, and export a parallel-coordinates payload
consumable by the UI.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> float:
    return time.time()


@dataclass
class ExperimentRecord:
    run_id: str
    experiment_id: str
    model_id: str
    metrics: Dict[str, float]
    params: Dict[str, Any]
    tags: Dict[str, str]
    created_at: float
    is_champion: bool = False


@dataclass
class ExperimentStore:
    records: List[ExperimentRecord] = field(default_factory=list)

    def add(self, record: ExperimentRecord) -> None:
        self.records.append(record)

    def by_experiment(
        self, experiment_id: str
    ) -> List[ExperimentRecord]:
        return [r for r in self.records if r.experiment_id == experiment_id]

    def by_model(self, model_id: str) -> List[ExperimentRecord]:
        return [r for r in self.records if r.model_id == model_id]


@dataclass
class LeaderboardEntry:
    run_id: str
    model_id: str
    primary_metric: str
    primary_value: float
    secondary_metrics: Dict[str, float]
    rank: int
    delta_to_champion: Optional[float] = None


def record_run(
    store: ExperimentStore,
    *,
    experiment_id: str,
    model_id: str,
    metrics: Mapping[str, float],
    params: Optional[Mapping[str, Any]] = None,
    tags: Optional[Mapping[str, str]] = None,
    is_champion: bool = False,
    run_id: Optional[str] = None,
    created_at: Optional[float] = None,
) -> ExperimentRecord:
    rec = ExperimentRecord(
        run_id=run_id or _new_id(),
        experiment_id=experiment_id,
        model_id=model_id,
        metrics=dict(metrics),
        params=dict(params or {}),
        tags=dict(tags or {}),
        created_at=created_at if created_at is not None else _now(),
        is_champion=is_champion,
    )
    store.add(rec)
    return rec


def leaderboard(
    store: ExperimentStore,
    experiment_id: str,
    primary_metric: str,
    *,
    higher_is_better: bool = True,
    top_k: Optional[int] = None,
    model_filter: Optional[Sequence[str]] = None,
) -> List[LeaderboardEntry]:
    rows = store.by_experiment(experiment_id)
    if model_filter is not None:
        flt = set(model_filter)
        rows = [r for r in rows if r.model_id in flt]
    if not rows:
        return []
    if primary_metric not in rows[0].metrics:
        return []
    ordered = sorted(
        rows,
        key=lambda r: r.metrics[primary_metric],
        reverse=higher_is_better,
    )
    if top_k is not None:
        ordered = ordered[:top_k]
    champion_value = None
    for r in rows:
        if r.is_champion:
            champion_value = r.metrics[primary_metric]
            break
    entries: List[LeaderboardEntry] = []
    for rank, rec in enumerate(ordered, start=1):
        secondaries = {
            k: v for k, v in rec.metrics.items() if k != primary_metric
        }
        delta = None
        if champion_value is not None and not rec.is_champion:
            delta = rec.metrics[primary_metric] - champion_value
        entries.append(
            LeaderboardEntry(
                run_id=rec.run_id,
                model_id=rec.model_id,
                primary_metric=primary_metric,
                primary_value=rec.metrics[primary_metric],
                secondary_metrics=secondaries,
                rank=rank,
                delta_to_champion=delta,
            )
        )
    return entries


def summarise_metrics(
    store: ExperimentStore,
    experiment_id: str,
    metric: str,
) -> Dict[str, float]:
    rows = store.by_experiment(experiment_id)
    vals = [r.metrics[metric] for r in rows if metric in r.metrics]
    if not vals:
        return {"n": 0.0, "mean": float("nan"), "std": float("nan"),
                "min": float("nan"), "max": float("nan")}
    arr = np.asarray(vals, dtype=float)
    return {
        "n": float(len(vals)),
        "mean": float(arr.mean()),
        "std": float(arr.std(ddof=0)) if len(vals) > 1 else 0.0,
        "min": float(arr.min()),
        "max": float(arr.max()),
    }


def parallel_coordinates_payload(
    store: ExperimentStore,
    experiment_id: str,
    metric_columns: Sequence[str],
) -> Dict[str, Any]:
    """Build a payload for parallel-coords visualisation."""
    rows = store.by_experiment(experiment_id)
    return {
        "experiment_id": experiment_id,
        "metrics": list(metric_columns),
        "points": [
            {
                "run_id": r.run_id,
                "model_id": r.model_id,
                **{m: r.metrics.get(m, float("nan")) for m in metric_columns},
            }
            for r in rows
        ],
    }


# numpy is referenced above; ensure the module-level import is
# added if it wasn't already pulled in.  A redundant import is a
# no-op so the call below is safe.
try:
    import numpy as np  # noqa: F401
except Exception:  # pragma: no cover
    import numpy as np  # type: ignore
