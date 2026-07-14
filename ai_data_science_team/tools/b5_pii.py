"""
b5_pii
=====

Deterministic PII detection + anonymisation tools supporting
**B5 — PII Detection & Anonymization** (spec
``docs/specs/B5-pii-detection.md``).

This module is the LLM-free core. The presidio-analyzer / spaCy NER
layer is owned by ``agents/pii_agent.py`` and only reachable when the
LLM-runtime is selected. The deterministic core is enough for the
spec's acceptance scenarios:

  * column-level scan with regex + light heuristics (TCKN,
    Turkish phone, e-mail, IBAN, NAME hints);
  * column-level anonymisation with four named strategies
    (``mask`` / ``hash`` / ``tokenize`` / ``drop``);
  * a per-column PII tag + confidence that the B5 catalog badge
    inherits from.

The interface matches the spec's ``pii.scan`` and
``pii.anonymize`` node contracts so the higher-level agent can
delegate or override as needed.

Public surface
--------------

* :func:`scan_pii(df, *, sample_rows=1000)` — ``PIIScanReport``.
* :func:`anonymize_dataframe(df, strategies, *, scan=None)` —
  ``AnonymisationResult``.
* :func:`default_strategies_for(scan)` — heuristic per-column
  recommendations.
* :func:`B5_PII_TOOL_NAMES` — registry constant.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# PII detectors (regex-based; TR-specific)
# ---------------------------------------------------------------------------


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TR_PHONE_RE = re.compile(
    r"^(?:\+?90|0)?\s?5\d{2}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}$"
)
_TCKN_RE = re.compile(r"^\d{11}$")
_IBAN_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{12,30}$")


PII_TYPES: Dict[str, Dict[str, Any]] = {
    "EMAIL_ADDRESS": {"regex": _EMAIL_RE, "name_hint": "email", "severity": "high"},
    "TR_PHONE": {"regex": _TR_PHONE_RE, "name_hint": "phone", "severity": "high"},
    "TR_ID_NUMBER": {"regex": _TCKN_RE, "name_hint": "tckn", "severity": "high"},
    "IBAN": {"regex": _IBAN_RE, "name_hint": "iban", "severity": "high"},
    "PERSON": {"regex": None, "name_hint": "name", "severity": "medium"},
}


_NAME_HINTS: Dict[str, str] = {
    "email": "EMAIL_ADDRESS",
    "e_mail": "EMAIL_ADDRESS",
    "mail": "EMAIL_ADDRESS",
    "phone": "TR_PHONE",
    "telefon": "TR_PHONE",
    "tel": "TR_PHONE",
    "mobile": "TR_PHONE",
    "gsm": "TR_PHONE",
    "tckn": "TR_ID_NUMBER",
    "tc_kimlik": "TR_ID_NUMBER",
    "identity": "TR_ID_NUMBER",
    "ssn": "TR_ID_NUMBER",
    "iban": "IBAN",
    "account": "IBAN",
    "name": "PERSON",
    "first_name": "PERSON",
    "last_name": "PERSON",
    "ad": "PERSON",
    "soyad": "PERSON",
    "adres": "PERSON",
    "address": "PERSON",
}


def _column_name_signal(name: str) -> Optional[str]:
    n = (name or "").lower().replace("-", "_").strip()
    tokens = [t for t in re.split(r"[_\s]+", n) if t]
    for tok in tokens:
        if tok in _NAME_HINTS:
            return _NAME_HINTS[tok]
    return None


def _match_ratio(series: pd.Series, regex: re.Pattern, *, sample: int) -> float:
    sample_strings = series.dropna().astype(str).head(sample).tolist()
    if not sample_strings:
        return 0.0
    matches = sum(1 for s in sample_strings if regex.match(s.strip()))
    return matches / len(sample_strings)


# ---------------------------------------------------------------------------
# Scan report
# ---------------------------------------------------------------------------


@dataclass
class ColumnPIIFinding:
    column: str
    pii_type: Optional[str]
    confidence: float
    match_ratio: float
    severity: str
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "column": self.column,
            "pii_type": self.pii_type,
            "confidence": float(self.confidence),
            "match_ratio": float(self.match_ratio),
            "severity": self.severity,
            "evidence": list(self.evidence[:5]),
        }


@dataclass
class PIIScanReport:
    n_rows_scanned: int
    findings: List[ColumnPIIFinding]
    pii_columns: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_rows_scanned": self.n_rows_scanned,
            "pii_columns": list(self.pii_columns),
            "findings": [f.to_dict() for f in self.findings],
        }


def scan_pii(df: pd.DataFrame, *, sample_rows: int = 1000) -> PIIScanReport:
    """Detect PII columns in a DataFrame.

    A column is flagged as PII when either:
      * its name suggests a known PII label, or
      * ≥ 30 % of its sampled values match a PII regex.
    """
    sample = max(1, int(sample_rows))
    n_rows = min(int(df.shape[0]), sample) if df.shape[0] else 0
    findings: List[ColumnPIIFinding] = []
    pii_columns: List[str] = []

    for col in df.columns:
        if isinstance(col, str) and col.startswith("__"):
            continue
        col_name = str(col)
        series = df[col]
        best_match_ratio = 0.0
        best_type: Optional[str] = None
        evidence: List[str] = []
        # Numeric columns won't match string regexes; skip regex sweep.
        string_series = (
            series.dropna().astype(str)
            if not pd.api.types.is_numeric_dtype(series)
            else pd.Series([], dtype=str)
        )
        for pii_type, info in PII_TYPES.items():
            regex = info["regex"]
            if regex is None or string_series.empty:
                continue
            ratio = _match_ratio(series, regex, sample=sample)
            if ratio > best_match_ratio:
                best_match_ratio = ratio
                best_type = pii_type
                evidence = string_series.head(min(3, sample)).tolist()

        name_type = _column_name_signal(col_name)
        if name_type and best_match_ratio < 0.30:
            best_match_ratio = max(best_match_ratio, 0.45)
            best_type = name_type

        if best_match_ratio >= 0.30 or name_type is not None:
            severity = (
                PII_TYPES.get(best_type or name_type, {}).get("severity", "low")
                if (best_type or name_type) in PII_TYPES
                else "low"
            )
            findings.append(
                ColumnPIIFinding(
                    column=col_name,
                    pii_type=best_type or name_type,
                    confidence=float(min(best_match_ratio, 1.0)),
                    match_ratio=float(best_match_ratio),
                    severity=severity,
                    evidence=evidence,
                )
            )
            pii_columns.append(col_name)
        else:
            findings.append(
                ColumnPIIFinding(
                    column=col_name,
                    pii_type=None,
                    confidence=0.0,
                    match_ratio=float(best_match_ratio),
                    severity="none",
                )
            )

    return PIIScanReport(
        n_rows_scanned=int(n_rows),
        findings=findings,
        pii_columns=pii_columns,
    )


# ---------------------------------------------------------------------------
# Anonymisation
# ---------------------------------------------------------------------------


def _mask_email(value: str, keep_domain: bool = False) -> str:
    if "@" not in value:
        # Generic mask keeps the last char hint.
        return value[:1] + "***" + value[-1:] if value else "***"
    local, _, domain = value.partition("@")
    if keep_domain:
        return "***@" + domain
    return "***@***"


def _mask_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 4:
        return "***"
    return "*" * (len(digits) - 4) + digits[-4:]


def _mask_generic(value: str) -> str:
    if not value:
        return "***"
    if len(value) <= 2:
        return "***"
    return value[0] + "***" + value[-1:]


def _hash_value(
    value: str,
    *,
    salt: str = "",
    algo: str = "sha256",
) -> str:
    payload = (salt + value).encode("utf-8")
    if algo == "md5":
        digest = hashlib.md5(payload).hexdigest()
    elif algo == "hmac-sha256":
        digest = hmac.new(
            salt.encode("utf-8"), value.encode("utf-8"), hashlib.sha256
        ).hexdigest()
    else:
        digest = hashlib.sha256(payload).hexdigest()
    return digest[:16]


def _tokenize_value(value: str, *, salt: str = "default") -> str:
    """Deterministic reversible-looking placeholder (non-reversible)."""
    digest = hashlib.sha256((salt + value).encode("utf-8")).hexdigest()[:8]
    return f"<TOK_{digest}>"


# Per-PII-type default maskers.
_MASK_BY_PII_TYPE: Dict[str, str] = {
    "EMAIL_ADDRESS": "mask_email",
    "TR_PHONE": "mask_phone",
    "TR_ID_NUMBER": "hash",
    "IBAN": "mask_generic_last_4",
}


def _mask_for(value: str, pii_type: Optional[str], strategy: str, params: Mapping[str, Any]) -> str:
    s = strategy.lower()
    if s == "mask":
        if pii_type == "EMAIL_ADDRESS":
            return _mask_email(value, keep_domain=bool(params.get("keep_domain", False)))
        if pii_type == "TR_PHONE":
            return _mask_phone(value)
        if pii_type == "IBAN":
            tail = value[-4:] if len(value) >= 4 else ""
            return "*" * (max(len(value) - 4, 0)) + tail
        return _mask_generic(value)
    if s == "hash":
        return _hash_value(value, salt=str(params.get("salt", "")), algo=str(params.get("algo", "sha256")))
    if s == "tokenize":
        return _tokenize_value(value, salt=str(params.get("salt", "default")))
    if s == "drop":
        return ""
    # Fallback: leave untouched.
    return value


def _default_strategy(pii_type: str) -> str:
    return _MASK_BY_PII_TYPE.get(pii_type, "mask")


def default_strategies_for(scan: PIIScanReport) -> Dict[str, Dict[str, Any]]:
    """Return default per-column strategies derived from a scan."""
    strategies: Dict[str, Dict[str, Any]] = {}
    for f in scan.findings:
        if f.pii_type is None:
            continue
        strategies[f.column] = {
            "pii_type": f.pii_type,
            "strategy": _default_strategy(f.pii_type),
            "params": {},
        }
    return strategies


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class AnonymisationResult:
    df: pd.DataFrame
    actions: List[Dict[str, Any]]
    failed_columns: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actions": list(self.actions),
            "failed_columns": list(self.failed_columns),
        }


def anonymize_dataframe(
    df: pd.DataFrame,
    strategies: Mapping[str, Mapping[str, Any]],
    *,
    scan: Optional[PIIScanReport] = None,
    fail_on_unhandled_pii: bool = False,
) -> AnonymisationResult:
    """Apply per-column anonymisation strategies.

    Parameters
    ----------
    df : pd.DataFrame
    strategies : mapping
        ``{column: {"pii_type": str, "strategy": str, "params": dict}}``.
        Recognised strategies: ``mask`` / ``hash`` / ``tokenize`` /
        ``drop``. ``pii_type`` is optional but recommended so per-PII
        masking can pick the right helper.
    scan : PIIScanReport, optional
        When supplied, columns flagged in ``scan.pii_columns`` that
        aren't in ``strategies`` either trigger ``fail_on_unhandled_pii``
        or fall through unmasked.
    fail_on_unhandled_pii : bool
        When True, raise ``ValueError`` on unhandled PII columns;
        when False, emit a warning ``actions`` entry and leave
        the column untouched.
    """
    out = df.copy()
    actions: List[Dict[str, Any]] = []
    failed: List[str] = []

    pii_columns = set(scan.pii_columns) if scan else set()
    handled_columns: set[str] = set()

    for col, spec in strategies.items():
        if col not in out.columns:
            continue
        strategy = str(spec.get("strategy", "mask")).lower()
        params = spec.get("params") or {}
        pii_type = spec.get("pii_type")

        def _mask_fn(v: Any) -> Any:
            if v is None or (isinstance(v, float) and np.isnan(v)):
                return v
            return _mask_for(str(v), pii_type, strategy, params)

        before = out[col].copy()
        out[col] = out[col].map(_mask_fn)
        n_changed = int((before != out[col]).sum())
        actions.append(
            {
                "column": str(col),
                "strategy": strategy,
                "pii_type": pii_type,
                "rows_changed": n_changed,
            }
        )
        handled_columns.add(str(col))

    if fail_on_unhandled_pii:
        leftover = sorted(pii_columns - handled_columns)
        if leftover:
            raise ValueError(
                f"unhandled PII columns: {leftover} (pass fail_on_unhandled_pii=False to ignore)"
            )

    if not fail_on_unhandled_pii and scan is not None:
        for col in sorted(pii_columns - handled_columns):
            actions.append(
                {
                    "column": col,
                    "strategy": "skipped",
                    "pii_type": None,
                    "rows_changed": 0,
                    "warning": "PII column not in strategies; left untouched",
                }
            )
            failed.append(col)

    return AnonymisationResult(df=out, actions=actions, failed_columns=failed)


__all__ = [
    "ColumnPIIFinding",
    "PIIScanReport",
    "scan_pii",
    "default_strategies_for",
    "AnonymisationResult",
    "anonymize_dataframe",
    "B5_PII_TOOL_NAMES",
]


B5_PII_TOOL_NAMES = [
    "b5_scan_pii",
    "b5_default_strategies",
    "b5_anonymize",
]
