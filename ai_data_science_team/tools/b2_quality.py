"""
b2_quality
==========

Deterministic statistical tools for **B2 — Data Validation / Kalite
Kapısı** (spec from ``docs/specs/B2-data-validation.md``).

Provides a Great-Expectations-flavoured expectation/suite engine so the
LLM-driven agent and the workflow runtime can check a dataset against a
user-defined suite (column types, value ranges, null rates, distribution
checks). The tools are pure-Python so they can be reused outside the
LangGraph runtime (workflow engine, batch jobs, ad-hoc notebooks).

Node type
---------
``data.validate``

The module exposes the following public functions:

* :func:`expectation_suite_from_template` — produce a starter suite for a
  dataset (column types + null rate + basic ranges).
* :func:`validate_against_suite` — run a suite against a dataset and
  return a per-rule result with pass/fail counts.
* :func:`summarise_suite_run` — human-readable summary plus overall
  status (``passed`` / ``failed`` / ``warning``).
"""

from __future__ import annotations

from typing import (
    Any,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
)

import pandas as pd


# ---------------------------------------------------------------------------
# Built-in expectation templates
# ---------------------------------------------------------------------------


TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    "customer_default": [
        {
            "kind": "column_type",
            "column": "email",
            "dtype": "object",
            "severity": "fail",
        },
        {
            "kind": "not_null",
            "column": "id",
            "severity": "fail",
        },
        {
            "kind": "value_range",
            "column": "age",
            "min": 0,
            "max": 130,
            "severity": "fail",
        },
        {
            "kind": "unique",
            "column": "id",
            "severity": "fail",
        },
    ],
    "transactions_default": [
        {"kind": "not_null", "column": "transaction_id", "severity": "fail"},
        {"kind": "unique", "column": "transaction_id", "severity": "fail"},
        {
            "kind": "value_range",
            "column": "amount",
            "min": 0,
            "max": 1_000_000,
            "severity": "fail",
        },
        {
            "kind": "null_rate",
            "column": "amount",
            "max_null_rate": 0.05,
            "severity": "warning",
        },
    ],
}


# ---------------------------------------------------------------------------
# Suite construction
# ---------------------------------------------------------------------------


def expectation_suite_from_template(
    template_name: str,
    dataset: pd.DataFrame,
    overrides: Optional[Mapping[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Generate a starter expectation suite for ``dataset``.

    Parameters
    ----------
    template_name : str
        One of :data:`TEMPLATES`.  Unknown names raise ``ValueError``.
    dataset : pd.DataFrame
        Used to infer column-specific fallback thresholds (e.g. min/max
        for ``value_range`` rules when a template does not specify them).
    overrides : mapping, optional
        Rule-level overrides applied after template expansion.  Keys are
        rule indices (``"0"``, ``"1"``, ...).  Useful for tightening
        numeric thresholds once the user inspects the data shape.

    Returns
    -------
    list of dict
        Each dict is an expectation rule ready to be fed into
        :func:`validate_against_suite`.
    """
    if template_name not in TEMPLATES:
        raise ValueError(
            f"Unknown template '{template_name}'. Known: "
            f"{sorted(TEMPLATES)}"
        )
    rules = [dict(r) for r in TEMPLATES[template_name]]
    # Drop rules whose column does not exist — caller may have a
    # dataset without 'email' or 'transaction_id' columns.  These are
    # surfaced in the validation summary as ``skipped``.
    out: List[Dict[str, Any]] = []
    for r in rules:
        col = r.get("column")
        if col is None or col in dataset.columns:
            out.append(r)
    if overrides:
        for k, v in overrides.items():
            try:
                idx = int(k)
                if 0 <= idx < len(out):
                    out[idx].update(v)
            except (ValueError, TypeError):
                continue
    return out


# ---------------------------------------------------------------------------
# Single-rule evaluation
# ---------------------------------------------------------------------------


def _eval_rule(
    df: pd.DataFrame,
    rule: Mapping[str, Any],
) -> Dict[str, Any]:
    """Evaluate one expectation rule against ``df``.

    Returns
    -------
    dict with keys ``kind``, ``column``, ``severity``, ``status``
    (``passed`` | ``failed`` | ``skipped`` | ``error``), ``observed``,
    ``violations`` (list of indices, capped) and ``threshold``.
    """
    kind = rule.get("kind")
    column = rule.get("column")
    severity = rule.get("severity", "fail")
    base: Dict[str, Any] = {
        "kind": kind,
        "column": column,
        "severity": severity,
        "status": "skipped",
        "observed": None,
        "violations": [],
        "threshold": {},
    }
    if column is None or column not in df.columns:
        base["status"] = "skipped"
        base["observed"] = None
        return base

    series = df[column]
    try:
        if kind == "not_null":
            nulls = int(series.isna().sum())
            passed = nulls == 0
            base.update(
                status="passed" if passed else "failed",
                observed={"null_count": nulls, "row_count": int(len(series))},
                violations=df.index[series.isna()].tolist()[:20],
                threshold={"max_null_count": 0},
            )
            return base
        if kind == "unique":
            dupes_mask = series.duplicated(keep=False) & series.notna()
            dup_count = int(dupes_mask.sum())
            passed = dup_count == 0
            base.update(
                status="passed" if passed else "failed",
                observed={"duplicate_count": dup_count},
                violations=df.index[dupes_mask].tolist()[:20],
                threshold={"max_duplicate_count": 0},
            )
            return base
        if kind == "column_type":
            expected_dtype = rule.get("dtype", "object")
            actual = str(series.dtype)
            # Pandas dtypes are fuzzy; allow some leeway.
            passed = _dtype_matches(actual, expected_dtype)
            base.update(
                status="passed" if passed else "failed",
                observed={"dtype": actual},
                threshold={"expected_dtype": expected_dtype},
            )
            return base
        if kind == "value_range":
            min_v = rule.get("min")
            max_v = rule.get("max")
            numeric = pd.to_numeric(series, errors="coerce")
            mask = (numeric < min_v) | (numeric > max_v) if (
                min_v is not None or max_v is not None
            ) else pd.Series(False, index=df.index)
            mask = mask.fillna(False)
            count = int(mask.sum())
            passed = count == 0
            base.update(
                status="passed" if passed else "failed",
                observed={
                    "out_of_range_count": count,
                    "min_observed": float(numeric.min(skipna=True)) if numeric.notna().any() else None,
                    "max_observed": float(numeric.max(skipna=True)) if numeric.notna().any() else None,
                },
                violations=df.index[mask].tolist()[:20],
                threshold={"min": min_v, "max": max_v},
            )
            return base
        if kind == "null_rate":
            max_null_rate = float(rule.get("max_null_rate", 0.05))
            null_rate = float(series.isna().mean()) if len(series) else 0.0
            passed = null_rate <= max_null_rate
            base.update(
                status="passed" if passed else "failed",
                observed={"null_rate": null_rate},
                violations=df.index[series.isna()].tolist()[:20],
                threshold={"max_null_rate": max_null_rate},
            )
            return base
        if kind == "regex_match":
            import re

            pattern = rule.get("pattern")
            if not pattern:
                base["status"] = "error"
                base["observed"] = {"error": "no pattern provided"}
                return base
            compiled = re.compile(pattern)
            non_null = series.dropna().astype(str)
            matches = non_null.map(lambda v: bool(compiled.fullmatch(v)))
            failed_mask = ~matches
            count = int(failed_mask.sum())
            passed = count == 0
            base.update(
                status="passed" if passed else "failed",
                observed={"non_matching_count": count},
                violations=df.index[df[column].astype(str).isin(
                    non_null[failed_mask]
                )].tolist()[:20],
                threshold={"pattern": pattern},
            )
            return base
        # Unknown rule kinds are surfaced as errors.
        base["status"] = "error"
        base["observed"] = {"error": f"unsupported kind '{kind}'"}
        return base
    except Exception as exc:  # noqa: BLE001
        base["status"] = "error"
        base["observed"] = {"error": repr(exc)}
        return base


def _dtype_matches(actual: str, expected: str) -> bool:
    """Soft-compare pandas dtypes — accept ``int64`` vs ``int`` etc."""
    a = actual.lower()
    e = expected.lower()
    if a == e:
        return True
    # object covers string/category; intX/int, floatX/float, etc.
    if "int" in a and "int" in e:
        return True
    if "float" in a and "float" in e:
        return True
    if "datetime" in a and "datetime" in e:
        return True
    if a.startswith("object") and e in {"str", "string", "object", "category"}:
        return True
    return False


# ---------------------------------------------------------------------------
# Suite-level evaluation
# ---------------------------------------------------------------------------


def validate_against_suite(
    df: pd.DataFrame,
    suite: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Validate ``df`` against ``suite`` and return a per-rule result.

    Parameters
    ----------
    df : pd.DataFrame
        Dataset to validate.
    suite : sequence of mapping
        Each entry is an expectation rule (see :data:`TEMPLATES`).

    Returns
    -------
    dict with keys ``passed`` (int), ``failed`` (int), ``warning`` (int),
    ``skipped`` (int), ``errors`` (int), ``rules`` (list of dict),
    ``dataset_shape`` (tuple).
    """
    rule_results: List[Dict[str, Any]] = []
    counts = {"passed": 0, "failed": 0, "warning": 0, "skipped": 0, "errors": 0}
    for rule in suite:
        r = _eval_rule(df, rule)
        rule_results.append(r)
        status = r["status"]
        if status == "passed":
            counts["passed"] += 1
        elif status == "failed":
            if r["severity"] == "warning":
                counts["warning"] += 1
            else:
                counts["failed"] += 1
        elif status == "skipped":
            counts["skipped"] += 1
        elif status == "error":
            counts["errors"] += 1
    return {
        "passed": counts["passed"],
        "failed": counts["failed"],
        "warning": counts["warning"],
        "skipped": counts["skipped"],
        "errors": counts["errors"],
        "rules": rule_results,
        "dataset_shape": list(df.shape),
    }


def summarise_suite_run(result: Mapping[str, Any]) -> Dict[str, Any]:
    """Aggregate :func:`validate_against_suite` output to a status string.

    Returns
    -------
    dict with keys ``status``, ``summary``, ``failed_severity``.
    """
    failed = int(result.get("failed", 0))
    warning = int(result.get("warning", 0))
    error = int(result.get("errors", 0))
    if failed > 0 or error > 0:
        status = "failed"
        failed_severity = "fail"
    elif warning > 0:
        status = "warning"
        failed_severity = "warning"
    elif int(result.get("passed", 0)) > 0:
        status = "passed"
        failed_severity = None
    else:
        status = "skipped"
        failed_severity = None
    summary = (
        f"{status.upper()}: "
        f"{result.get('passed', 0)} passed, "
        f"{result.get('failed', 0)} failed, "
        f"{result.get('warning', 0)} warning, "
        f"{result.get('skipped', 0)} skipped, "
        f"{result.get('errors', 0)} errors "
        f"on shape {tuple(result.get('dataset_shape', [0, 0]))}"
    )
    return {
        "status": status,
        "summary": summary,
        "failed_severity": failed_severity,
    }


__all__ = [
    "TEMPLATES",
    "expectation_suite_from_template",
    "validate_against_suite",
    "summarise_suite_run",
    "B2_VALIDATION_TOOL_NAMES",
]


B2_VALIDATION_TOOL_NAMES = [
    "b2_suite_from_template",
    "b2_validate",
    "b2_summarise",
]
