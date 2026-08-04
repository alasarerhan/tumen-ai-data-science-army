from __future__ import annotations

"""j4_eval_store. Deterministic model-evaluation storage / summary
tools. Implements J4 — record evaluation runs (dataset + model +
metrics + fairness slices), query by filter, compare 2-4 models,
summarise across datasets, slice by demographic / feature bucket.
"""

import math  # noqa: E402, F401
import time  # noqa: E402, F401
import uuid  # noqa: E402, F401
from dataclasses import dataclass, field  # noqa: E402, F401
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple  # noqa: E402, F401


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> float:
    return time.time()


@dataclass
class SliceMetrics:
    slice_name: str
    metrics: Dict[str, float]
    sample_size: int


@dataclass
class EvalRecord:
    eval_id: str
    model_id: str
    dataset_id: str
    metrics: Dict[str, float]
    slices: List[SliceMetrics]
    created_at: float
    notes: str = ""


@dataclass
class EvalStore:
    records: List[EvalRecord] = field(default_factory=list)

    def add(self, rec: EvalRecord) -> None:
        self.records.append(rec)

    def by_model(self, model_id: str) -> List[EvalRecord]:
        return [r for r in self.records if r.model_id == model_id]

    def by_dataset(self, dataset_id: str) -> List[EvalRecord]:
        return [r for r in self.records if r.dataset_id == dataset_id]


def record_evaluation(
    store: EvalStore,
    *,
    model_id: str,
    dataset_id: str,
    metrics: Mapping[str, float],
    slices: Optional[Sequence[Mapping[str, Any]]] = None,
    notes: str = "",
    eval_id: Optional[str] = None,
    created_at: Optional[float] = None,
) -> EvalRecord:
    parsed_slices = [
        SliceMetrics(
            slice_name=str(s["slice_name"]),
            metrics=dict(s.get("metrics", {})),
            sample_size=int(s.get("sample_size", 0)),
        )
        for s in (slices or [])
    ]
    rec = EvalRecord(
        eval_id=eval_id or _new_id(),
        model_id=model_id,
        dataset_id=dataset_id,
        metrics=dict(metrics),
        slices=parsed_slices,
        created_at=created_at if created_at is not None else _now(),
        notes=notes,
    )
    store.add(rec)
    return rec


def query_evaluations(
    store: EvalStore,
    *,
    model_ids: Optional[Sequence[str]] = None,
    dataset_ids: Optional[Sequence[str]] = None,
    metric_filter: Optional[Mapping[str, Tuple[float, float]]] = None,
) -> List[EvalRecord]:
    out = list(store.records)
    if model_ids is not None:
        ms = set(model_ids)
        out = [r for r in out if r.model_id in ms]
    if dataset_ids is not None:
        ds = set(dataset_ids)
        out = [r for r in out if r.dataset_id in ds]
    if metric_filter is not None:
        kept = []
        for r in out:
            ok = True
            for m, (lo, hi) in metric_filter.items():
                v = r.metrics.get(m)
                if v is None or v < lo or v > hi:
                    ok = False
                    break
            if ok:
                kept.append(r)
        out = kept
    return out


def compare_models(
    store: EvalStore,
    model_ids: Sequence[str],
    dataset_id: str,
    metrics: Sequence[str],
) -> Dict[str, Dict[str, float]]:
    """Build a {model_id: {metric: value}} comparison dict on a
    single dataset."""
    if len(model_ids) < 2:
        raise ValueError("compare_models requires >=2 model_ids")
    if len(model_ids) > 4:
        raise ValueError("compare_models supports at most 4 models")
    out: Dict[str, Dict[str, float]] = {m: {} for m in model_ids}
    for r in store.records:
        if r.dataset_id != dataset_id:
            continue
        if r.model_id not in out:
            continue
        for m in metrics:
            if m in r.metrics:
                out[r.model_id][m] = r.metrics[m]
    return out


def summarise_over_datasets(
    store: EvalStore,
    model_id: str,
    metric: str,
) -> Dict[str, float]:
    vals = [r.metrics[metric] for r in store.by_model(model_id) if metric in r.metrics]
    if not vals:
        return {
            "n": 0.0,
            "mean": float("nan"),
            "min": float("nan"),
            "max": float("nan"),
            "std": float("nan"),
        }
    arr = list(vals)
    n = len(arr)
    mean = sum(arr) / n
    var = sum((v - mean) ** 2 for v in arr) / n
    return {
        "n": float(n),
        "mean": float(mean),
        "min": float(min(arr)),
        "max": float(max(arr)),
        "std": float(math.sqrt(var)),
    }


def slice_by_feature(
    store: EvalStore,
    *,
    model_id: str,
    dataset_id: str,
    slice_name: Optional[str] = None,
) -> Dict[str, Dict[str, float]]:
    """Return aggregated metric values for each slice, optionally
    filtered by slice name."""
    out: Dict[str, Dict[str, float]] = {}
    for r in store.records:
        if r.model_id != model_id or r.dataset_id != dataset_id:
            continue
        for s in r.slices:
            if slice_name is not None and s.slice_name != slice_name:
                continue
            bucket = out.setdefault(s.slice_name, {})
            for m, v in s.metrics.items():
                bucket[m] = bucket.get(m, 0.0) + v
    return out
