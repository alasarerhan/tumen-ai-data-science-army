"""
b7_data_ingestion
=================

Deterministic tools supporting **B7 — Data Ingestion / ELT** (spec
``docs/specs/B7-data-ingestion.md``).

Provides the deterministic core of the data-ingestion engine:
watermark tracking, job registration, run history, and
incremental-load diffing.

Public surface
--------------

* :func:`register_ingest_job` — produce a normalised ingest-job dict.
* :func:`compute_watermark` — evaluate a watermark target against
  the last known high-water mark.
* :func:`incremental_diff` — classify rows between baseline + current
  DataFrames as added/removed/changed.
* :func:`record_run` — produce a run-history row.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd


# ---------------------------------------------------------------------------
# Job registry
# ---------------------------------------------------------------------------


@dataclass
class IngestJob:
    job_id: str
    name: str
    source: str
    target: str
    incremental_key: Optional[str] = None
    schedule: Optional[str] = None  # cron-style or relative
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "source": self.source,
            "target": self.target,
            "incremental_key": self.incremental_key,
            "schedule": self.schedule,
            "created_at": self.created_at,
        }


def register_ingest_job(
    name: str,
    source: str,
    target: str,
    *,
    job_id: Optional[str] = None,
    incremental_key: Optional[str] = None,
    schedule: Optional[str] = None,
    created_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Materialise an ingest-job record for the workflow registry."""
    import uuid as _uuid

    return IngestJob(
        job_id=job_id or _uuid.uuid4().hex,
        name=name,
        source=source,
        target=target,
        incremental_key=incremental_key,
        schedule=schedule,
        created_at=created_at,
    ).to_dict()


# ---------------------------------------------------------------------------
# Watermark tracking
# ---------------------------------------------------------------------------


@dataclass
class WatermarkState:
    job_id: str
    last_high_water: Any
    next_high_water: Any
    delta_rows: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "last_high_water": self.last_high_water,
            "next_high_water": self.next_high_water,
            "delta_rows": self.delta_rows,
        }


def _key_tuples(idx, key_only):
    """Coerce a pandas Index (single or multi) into a list of tuple keys."""
    out = []
    for entry in idx:
        if isinstance(entry, tuple):
            out.append(entry)
        else:
            out.append((entry,))
    return out


def compute_watermark(
    job_id: str,
    previous: Any,
    current: Any,
    *,
    delta_rows: int = 0,
) -> WatermarkState:
    """Return a watermark-progress record.

    Accepts any comparable types: ``previous`` is the high-water mark
    stored in the registry after the last successful ingest,
    ``current`` is the highest watermark in the new batch. The
    function records both states verbatim — monotonicity is the
    caller's responsibility (so multi-source watermarks with mixed
    ``datetime`` / ``int`` types still work).
    """
    return WatermarkState(
        job_id=job_id,
        last_high_water=previous,
        next_high_water=current,
        delta_rows=int(delta_rows),
    )


# ---------------------------------------------------------------------------
# Incremental diff
# ---------------------------------------------------------------------------


def incremental_diff(
    baseline: pd.DataFrame,
    current: pd.DataFrame,
    *,
    key_columns: Optional[Sequence[str]] = None,
    compare_columns: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Diff two DataFrames for watermark-style incremental loads.

    Parameters
    ----------
    baseline : pd.DataFrame
        The previously-loaded snapshot.
    current : pd.DataFrame
        The freshly-loaded snapshot.
    key_columns : sequence of str, optional
        Columns that uniquely identify a row. Defaults to the index.
    compare_columns : sequence of str, optional
        Subset of columns whose values matter for the "changed"
        classification; falls back to all shared columns.

    Returns
    -------
    dict with keys ``added``, ``removed``, ``changed`` (lists of
    key tuples) and ``n_added``, ``n_removed``, ``n_changed``
    counters. ``added`` rows are present in ``current`` but not in
    ``baseline``; the reverse holds for ``removed``.
    """
    baseline = baseline.copy()
    current = current.copy()
    if key_columns is None:
        # Position-based: row identity is the integer row index.
        baseline = baseline.reset_index(drop=True)
        current = current.reset_index(drop=True)
        baseline.insert(0, "__rowid__", range(len(baseline)))
        current.insert(0, "__rowid__", range(len(current)))
        key_columns = ["__rowid__"]
        compare_columns_final = list(
            compare_columns if compare_columns is not None
            else [c for c in baseline.columns if c != "__rowid__"]
        )
        # Strip the synthetic column from the keys.
        key_only = ["__rowid__"]
    else:
        compare_columns_final = list(
            compare_columns if compare_columns is not None
            else sorted(set(baseline.columns) & set(current.columns))
        )
        key_only = list(key_columns)

    if compare_columns is not None:
        pass
    # Align the two frames on the key columns. Keep a separate
    # ``__keys__`` column for fast set comparison; the index may be a
    # single scalar when key_only is len 1 and pandas flattens it.
    base_view = baseline.set_index(key_only)
    curr_view = current.set_index(key_only)
    base_view = base_view.assign(__keys__=_key_tuples(base_view.index, key_only))
    curr_view = curr_view.assign(__keys__=_key_tuples(curr_view.index, key_only))

    base_keys = set(base_view["__keys__"].tolist())
    curr_keys = set(curr_view["__keys__"].tolist())
    added_keys = curr_keys - base_keys
    removed_keys = base_keys - curr_keys
    common_keys = base_keys & curr_keys

    changed: List[Tuple[Any, ...]] = []
    for k in common_keys:
        if isinstance(k, tuple):
            selector = list(k)
        else:
            selector = k
        try:
            b_row = base_view.loc[selector]
            c_row = curr_view.loc[selector]
        except Exception:  # noqa: BLE001
            # The key tuple wasn't found in this frame (race with
            # case-folding or dtype); skip.
            continue
        if isinstance(b_row, pd.DataFrame):
            b_row = b_row.iloc[0]
            c_row = c_row.iloc[0]
        # Compare the relevant columns.
        b_vals = {c: b_row[c] for c in compare_columns_final if c in base_view.columns}
        c_vals = {c: c_row[c] for c in compare_columns_final if c in curr_view.columns}
        if b_vals != c_vals:
            changed.append(k)

    return {
        "added": sorted(added_keys),
        "removed": sorted(removed_keys),
        "changed": sorted(changed),
        "n_added": len(added_keys),
        "n_removed": len(removed_keys),
        "n_changed": len(changed),
    }


# ---------------------------------------------------------------------------
# Run history
# ---------------------------------------------------------------------------


@dataclass
class RunRow:
    job_id: str
    run_id: str
    status: str  # "success" | "failed" | "running"
    started_at: str
    finished_at: Optional[str] = None
    rows_loaded: int = 0
    error: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "run_id": self.run_id,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "rows_loaded": self.rows_loaded,
            "error": self.error,
            "notes": self.notes,
        }


def record_run(
    job_id: str,
    run_id: str,
    status: str,
    started_at: str,
    *,
    finished_at: Optional[str] = None,
    rows_loaded: int = 0,
    error: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a single run-history row."""
    return RunRow(
        job_id=job_id,
        run_id=run_id,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        rows_loaded=int(rows_loaded),
        error=error,
        notes=notes,
    ).to_dict()


__all__ = [
    "register_ingest_job",
    "compute_watermark",
    "incremental_diff",
    "record_run",
]


