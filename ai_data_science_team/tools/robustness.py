from __future__ import annotations

"""f5_robustness. Deterministic robustness-test tools. Implements
the F5 spec — perturbation (Gaussian noise), feature masking,
and synthetic edge-case evaluation that produces a
``model x scenario`` performance matrix.
"""

from dataclasses import dataclass  # noqa: E402, F401
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple  # noqa: E402, F401

import numpy as np  # noqa: E402, F401
import pandas as pd  # noqa: E402, F401


# ---------------------------------------------------------------------------
# Perturbation primitives
# ---------------------------------------------------------------------------


def _accuracy(y_true, y_pred) -> float:
    a = np.asarray(y_true).astype(int)
    b = np.asarray(y_pred).astype(int)
    if a.size == 0:
        return 0.0
    return float((a == b).mean())


def add_gaussian_noise(
    X: np.ndarray, *, sigma: float = 0.1, rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Add N(0, sigma) noise to numeric columns of ``X``.

    Accepts only numeric dtype.  Integer columns are promoted to
    float for the perturbation step.
    """
    if not isinstance(X, np.ndarray):
        X = np.asarray(X, dtype=float)
    if X.dtype.kind not in "fiub":
        # Non-numeric array: return as float for downstream metrics.
        return X.astype(float)
    rng = rng or np.random.default_rng(0)
    noise = rng.normal(0.0, sigma, size=X.shape).astype(X.dtype, copy=False)
    return X.astype(float) + noise.astype(float)


def mask_features(
    X: np.ndarray, mask_rate: float = 0.3, *,
    fill_value: float = 0.0, rng: np.random.Generator | None = None,
    columns: Optional[Sequence[int]] = None,
) -> np.ndarray:
    """Randomly mask ``mask_rate`` of cells to ``fill_value``."""
    if not isinstance(X, np.ndarray):
        X = np.asarray(X, dtype=float)
    X = X.astype(float)
    rng = rng or np.random.default_rng(0)
    out = X.copy()
    cols = list(columns) if columns else list(range(X.shape[1]))
    for c in cols:
        n = X.shape[0]
        idx = rng.choice(n, size=int(round(mask_rate * n)), replace=False)
        out[idx, c] = fill_value
    return out


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


@dataclass
class Scenario:
    name: str
    transform: Callable[[np.ndarray, np.ndarray], np.ndarray]
    description: str = ""

    def apply(self, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        return self.transform(X, y)


def default_scenarios(
    sigma_levels: Sequence[float] = (0.05, 0.1, 0.2),
    mask_levels: Sequence[float] = (0.1, 0.3, 0.5),
) -> List[Scenario]:
    """Return the spec's default scenario set."""
    out: List[Scenario] = [
        Scenario(
            "clean",
            lambda X, y: X,
            "no perturbation",
        ),
        Scenario(
            "edge_case_min_features",
            lambda X, y: np.zeros_like(X) if X.size else X,
            "all features zeroed",
        ),
        Scenario(
            "edge_case_max_features",
            lambda X, y: np.full_like(X, 1e6) if X.size else X,
            "extreme-magnitude features",
        ),
    ]
    for s in sigma_levels:
        out.append(
            Scenario(
                f"noise_sigma_{s}",
                lambda X, y, s=s: add_gaussian_noise(X, sigma=s),
                f"Gaussian noise sigma={s}",
            )
        )
    for m in mask_levels:
        out.append(
            Scenario(
                f"mask_{int(m*100)}pct",
                lambda X, y, m=m: mask_features(X, mask_rate=m),
                f"{int(m*100)}% feature mask",
            )
        )
    return out


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


@dataclass
class RobustnessResult:
    model_name: str
    metric: str
    matrix: pd.DataFrame  # scenarios x replicate_id
    summary: pd.DataFrame  # scenarios x {mean, std, delta_from_clean}
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        # Manual dict-of-dict serialisation.  ``DataFrame.to_dict``
        # returns values in pandas-version-dependent shapes (full
        # cartesian product of index × columns under some versions)
        # which produces mismatched counts.  Build it explicitly.
        return {
            "model_name": self.model_name,
            "metric": self.metric,
            "matrix": {
                str(idx): {str(c): v for c, v in row.items()}
                for idx, row in self.matrix.iterrows()
            },
            "summary": {
                str(idx): {k: v for k, v in row.items()}
                for idx, row in self.summary.iterrows()
            },
            "metadata": self.metadata,
        }


def evaluate_robustness(
    model_name: str,
    predict: Callable[[np.ndarray], np.ndarray],
    X: np.ndarray,
    y: np.ndarray,
    *,
    scenarios: Optional[Sequence[Scenario]] = None,
    replicates: int = 1,
    metric: str = "accuracy",
    seed: int = 0,
) -> RobustnessResult:
    """Run ``predict`` over each scenario ``replicates`` times.

    ``replicates`` is useful when a scenario uses random noise or
    masking; each replicate draws a fresh RNG.
    """
    rng = np.random.default_rng(seed)
    if scenarios is None:
        scenarios = default_scenarios()
    rows: Dict[Tuple[str, int], float] = {}

    for s in scenarios:
        for r in range(replicates):
            np.random.default_rng(int(rng.integers(0, 2**31 - 1)))
            X_perturbed = s.apply(X, y)  # uses module-level noise/mask
            y_pred = predict(X_perturbed)
            if metric == "accuracy":
                v = _accuracy(y, y_pred)
            else:
                # Fallback: caller-provided metric must accept y, y_pred.
                v = float(metric(y, y_pred))
            rows[(s.name, r)] = v

    unique_scenarios = list(dict.fromkeys(s for (s, _) in rows.keys()))
    matrix = pd.DataFrame(
        {r: [v for (s, rr), v in rows.items() if rr == r]
         for r in range(replicates)},
        index=unique_scenarios,
    )
    matrix.index.name = "scenario"

    summary_rows = []
    for s in scenarios:
        vals = [rows[(s.name, r)] for r in range(replicates)]
        clean_vals = rows.get(("clean", 0))
        delta = (
            float(np.mean(vals)) - clean_vals
            if clean_vals is not None
            else float("nan")
        )
        summary_rows.append(
            {
                "scenario": s.name,
                "mean": float(np.mean(vals)),
                "std": float(np.std(vals, ddof=0)) if len(vals) > 1 else 0.0,
                "delta_from_clean": delta,
                "n_replicates": replicates,
            }
        )
    summary = pd.DataFrame(summary_rows).set_index("scenario")

    return RobustnessResult(
        model_name=model_name,
        metric=metric,
        matrix=matrix,
        summary=summary,
        metadata={
            "replicates": replicates,
            "seed": seed,
            "n_samples": int(X.shape[0]),
            "n_features": int(X.shape[1]) if X.ndim > 1 else 0,
        },
    )


