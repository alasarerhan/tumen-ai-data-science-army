from __future__ import annotations

"""j11_shadow_canary. Deterministic shadow / canary deployment
tools. Implements J11 — register a deployment run (model + traffic
split + rollback policy), record live metrics for both champion
and challenger, evaluate auto-rollback thresholds, summarise the
deployment's status.
"""

import math  # noqa: E402, F401
import time  # noqa: E402, F401
import uuid  # noqa: E402, F401
from dataclasses import dataclass, field  # noqa: E402, F401
from typing import Any, Dict, List, Optional  # noqa: E402, F401


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> float:
    return time.time()


@dataclass
class RollbackPolicy:
    """Auto-rollback thresholds.

    * ``error_rate_max`` — if challenger's error rate exceeds this,
      rollback.
    * ``latency_p99_max_ms`` — if p99 latency exceeds this, rollback.
    * ``min_samples`` — number of live samples before evaluation
      becomes active (so cold-start doesn't trigger a rollback).
    """

    error_rate_max: float = 0.05
    latency_p99_max_ms: float = 500.0
    min_samples: int = 100


@dataclass
class LiveSample:
    variant: str  # "champion" or "challenger"
    latency_ms: float
    error: bool
    score: Optional[float] = None
    timestamp: float = 0.0


@dataclass
class Deployment:
    deployment_id: str
    challenger_model_id: str
    champion_model_id: str
    traffic_split: float  # 0.0..1.0 share to challenger
    mode: str  # "shadow" (no live traffic) or "canary" (live split)
    policy: RollbackPolicy
    samples: List[LiveSample] = field(default_factory=list)
    status: str = "running"  # "running" | "rolled_back" | "promoted"
    created_at: float = 0.0


@dataclass
class DeploymentStore:
    deployments: List[Deployment] = field(default_factory=list)

    def add(self, d: Deployment) -> None:
        self.deployments.append(d)


def start_deployment(
    store: DeploymentStore,
    *,
    challenger_model_id: str,
    champion_model_id: str,
    traffic_split: float,
    mode: str = "canary",
    error_rate_max: float = 0.05,
    latency_p99_max_ms: float = 500.0,
    min_samples: int = 100,
    deployment_id: Optional[str] = None,
) -> Deployment:
    if mode not in ("shadow", "canary"):
        raise ValueError("mode must be 'shadow' or 'canary'")
    if not 0.0 <= traffic_split <= 1.0:
        raise ValueError("traffic_split must be in [0.0, 1.0]")
    d = Deployment(
        deployment_id=deployment_id or _new_id(),
        challenger_model_id=challenger_model_id,
        champion_model_id=champion_model_id,
        traffic_split=traffic_split,
        mode=mode,
        policy=RollbackPolicy(
            error_rate_max=error_rate_max,
            latency_p99_max_ms=latency_p99_max_ms,
            min_samples=min_samples,
        ),
        created_at=_now(),
    )
    store.add(d)
    return d


def record_live_sample(
    store: DeploymentStore,
    deployment_id: str,
    *,
    variant: str,
    latency_ms: float,
    error: bool,
    score: Optional[float] = None,
    timestamp: Optional[float] = None,
) -> None:
    if variant not in ("champion", "challenger"):
        raise ValueError("variant must be 'champion' or 'challenger'")
    for d in store.deployments:
        if d.deployment_id == deployment_id:
            d.samples.append(
                LiveSample(
                    variant=variant,
                    latency_ms=float(latency_ms),
                    error=bool(error),
                    score=score,
                    timestamp=timestamp if timestamp is not None else _now(),
                )
            )
            return
    raise KeyError(f"deployment_id not found: {deployment_id}")


def evaluate_rollback(store: DeploymentStore, deployment_id: str) -> Dict[str, Any]:
    """Evaluate auto-rollback thresholds for a deployment. Returns
    a structured dict with verdict + reasons. Does NOT mutate
    deployment status — caller decides."""
    d = next(
        (d for d in store.deployments if d.deployment_id == deployment_id),
        None,
    )
    if d is None:
        raise KeyError(f"deployment_id not found: {deployment_id}")
    chall = [s for s in d.samples if s.variant == "challenger"]
    n = len(chall)
    reasons: List[str] = []
    if n < d.policy.min_samples:
        return {
            "deployment_id": deployment_id,
            "verdict": "insufficient_data",
            "samples": n,
            "min_samples": d.policy.min_samples,
            "reasons": [f"need {d.policy.min_samples} samples, have {n}"],
        }
    err_rate = sum(1 for s in chall if s.error) / n
    if err_rate > d.policy.error_rate_max:
        reasons.append(f"error_rate {err_rate:.4f} > {d.policy.error_rate_max:.4f}")
    latencies = sorted(s.latency_ms for s in chall)
    p99_idx = max(0, int(math.ceil(0.99 * n)) - 1)
    p99 = latencies[p99_idx] if latencies else 0.0
    if p99 > d.policy.latency_p99_max_ms:
        reasons.append(f"latency_p99 {p99:.1f}ms > {d.policy.latency_p99_max_ms:.1f}ms")
    return {
        "deployment_id": deployment_id,
        "verdict": "rollback" if reasons else "ok",
        "samples": n,
        "error_rate": err_rate,
        "latency_p99_ms": p99,
        "reasons": reasons,
    }


def mark_status(store: DeploymentStore, deployment_id: str, status: str) -> None:
    if status not in ("running", "rolled_back", "promoted"):
        raise ValueError("status must be running/rolled_back/promoted")
    for d in store.deployments:
        if d.deployment_id == deployment_id:
            d.status = status
            return
    raise KeyError(f"deployment_id not found: {deployment_id}")


def summarise_deployment(store: DeploymentStore, deployment_id: str) -> Dict[str, Any]:
    d = next(
        (d for d in store.deployments if d.deployment_id == deployment_id),
        None,
    )
    if d is None:
        raise KeyError(f"deployment_id not found: {deployment_id}")
    by_variant: Dict[str, Dict[str, float]] = {}
    for variant in ("champion", "challenger"):
        rows = [s for s in d.samples if s.variant == variant]
        if not rows:
            by_variant[variant] = {
                "n": 0.0,
                "error_rate": float("nan"),
                "latency_mean_ms": float("nan"),
                "latency_p99_ms": float("nan"),
                "score_mean": float("nan"),
            }
            continue
        n = len(rows)
        err = sum(1 for s in rows if s.error) / n
        lats = sorted(s.latency_ms for s in rows)
        lat_mean = sum(lats) / n
        p99_idx = max(0, int(math.ceil(0.99 * n)) - 1)
        scores = [s.score for s in rows if s.score is not None]
        score_mean = sum(scores) / len(scores) if scores else float("nan")
        by_variant[variant] = {
            "n": float(n),
            "error_rate": float(err),
            "latency_mean_ms": float(lat_mean),
            "latency_p99_ms": float(lats[p99_idx]),
            "score_mean": float(score_mean),
        }
    return {
        "deployment_id": deployment_id,
        "challenger_model_id": d.challenger_model_id,
        "champion_model_id": d.champion_model_id,
        "mode": d.mode,
        "traffic_split": d.traffic_split,
        "status": d.status,
        "by_variant": by_variant,
    }


def list_deployments(
    store: DeploymentStore,
    *,
    status: Optional[str] = None,
    mode: Optional[str] = None,
) -> List[Deployment]:
    out = list(store.deployments)
    if status is not None:
        out = [d for d in out if d.status == status]
    if mode is not None:
        out = [d for d in out if d.mode == mode]
    return out
