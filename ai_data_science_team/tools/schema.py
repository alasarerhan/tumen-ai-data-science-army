from __future__ import annotations

"""
b3_schema
=========

Deterministic schema-inference + target-mapping tools for **B3 —
Schema Inference & Mapping** (spec
``docs/specs/B3-schema-inference.md``).

Two-phase deterministic core:

  * Phase A — ``infer_column_type``: deduce a logical type from
    pandas dtype + sample-pattern checks (date / time, currency,
    boolean, integer-as-string, percentage, ID).
  * Phase B — ``build_mapping``: match inferred source schema to
    a target schema via normalised-name similarity + type
    compatibility scoring.  When user corrections are supplied,
    they take precedence (the override + name memory).

Public surface
--------------

* :func:`infer_column_type(series, *, sample=10000)` → InferredType.
* :func:`infer_schema(df, *, sample=10000)` → Schema with per-column
  type, sample-count, normalise suggestions.
* :func:`build_mapping(source, target, *, corrections=None)` →
  MappingResult with per-source-column decision + confidence.
* :func:`mapping_summary(mapping)` → flat dict for downstream I/O.
"""

import re  # noqa: E402, F401
import unicodedata  # noqa: E402, F401
from dataclasses import dataclass, field  # noqa: E402, F401
from typing import Any, Dict, List, Mapping, Optional, Tuple  # noqa: E402, F401

import pandas as pd  # noqa: E402, F401


# ---------------------------------------------------------------------------
# Type inference
# ---------------------------------------------------------------------------


_DATE_PATTERNS = [
    re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    re.compile(r"^\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}(:\d{2})?$"),
    re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    re.compile(r"^\d{2}\.\d{2}\.\d{4}$"),
]
_TR_TIME_HHMM = re.compile(r"^\d{2}:\d{2}(:\d{2})?$")
# Currency: ₺/TL/USD/EUR followed by digits with . or , as group sep.
_CURRENCY_RE = re.compile(
    r"""^[€$£¥₺]\s?-?[\d.,]+$|^\d{1,3}([.,]\d{3})*([.,]\d{1,2})?\s?(TRY|USD|EUR|GBP|JPY|RUB)$""",
    re.UNICODE,
)
_PERCENT_RE = re.compile(r"^-?[\d.,]+\s?%$")
_BOOL_TOKENS = {"true", "false", "yes", "no", "y", "n", "0", "1", "t", "f"}


@dataclass
class InferredType:
    name: str  # "integer" | "float" | "string" | "date" | "datetime" | "time" | "boolean" | "currency" | "percent" | "id" | "categorical"
    confidence: float
    pandas_dtype: str
    transform: str  # applied (cast_*, parse_*, etc.)
    detected_currency: Optional[str] = None
    detected_pattern: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "confidence": float(self.confidence),
            "pandas_dtype": self.pandas_dtype,
            "transform": self.transform,
            "detected_currency": self.detected_currency,
            "detected_pattern": self.detected_pattern,
        }


def _normalise_string(s: str) -> str:
    n = unicodedata.normalize("NFKD", s)
    return "".join(c for c in n if not unicodedata.combining(c))


def _all_match(series: pd.Series, regex: re.Pattern, sample: int) -> bool:
    sample_strings = series.dropna().astype(str).head(sample).tolist()
    if not sample_strings:
        return False
    return all(regex.match(_normalise_string(s)) for s in sample_strings)


def _majority_match(series: pd.Series, regex: re.Pattern, sample: int, threshold: float = 0.7) -> bool:
    sample_strings = series.dropna().astype(str).head(sample).tolist()
    if not sample_strings:
        return False
    matches = sum(1 for s in sample_strings if regex.match(_normalise_string(s)))
    return matches / len(sample_strings) >= threshold


def infer_column_type(
    series: pd.Series,
    *,
    sample: int = 10000,
) -> InferredType:
    """Infer a logical type for one column.

    Order of checks:
      1. Pandas numeric/string/datetime dtype → fast-path.
      2. Boolean tokens if string dtype.
      3. Sample-pattern checks: date / time / percent / currency.
    """
    sample_size = min(int(sample), int(len(series)))
    if sample_size == 0:
        return InferredType(
            name="empty",
            confidence=0.0,
            pandas_dtype=str(series.dtype),
            transform="drop",
        )
    sub = series.head(sample_size)
    n = int(len(sub))

    # Fast-path: pandas already tells us.
    if pd.api.types.is_datetime64_any_dtype(sub):
        return InferredType(
            name="datetime",
            confidence=1.0,
            pandas_dtype=str(series.dtype),
            transform="parse_datetime",
        )
    if pd.api.types.is_integer_dtype(sub):
        # Treat near-unique integer columns as ``id`` candidates.
        unique_ratio = sub.nunique() / max(len(sub), 1)
        if unique_ratio > 0.95 and sub.min() >= 0:
            return InferredType(
                name="id",
                confidence=0.85,
                pandas_dtype=str(series.dtype),
                transform="cast_int",
            )
        return InferredType(
            name="integer",
            confidence=0.99,
            pandas_dtype=str(series.dtype),
            transform="cast_int",
        )
    if pd.api.types.is_float_dtype(sub):
        return InferredType(
            name="float",
            confidence=0.99,
            pandas_dtype=str(series.dtype),
            transform="cast_float",
        )

    string_series = sub.dropna().astype(str)
    if string_series.empty:
        return InferredType(
            name="empty",
            confidence=0.0,
            pandas_dtype=str(series.dtype),
            transform="drop",
        )

    cleaned_samples = [
        _normalise_string(s) for s in string_series.head(sample_size).tolist()
    ]    

    # Boolean first (cheap check).
    lowered = [s.strip().lower() for s in cleaned_samples]
    if all(s in _BOOL_TOKENS for s in lowered):
        return InferredType(
            name="boolean",
            confidence=0.99,
            pandas_dtype=str(series.dtype),
            transform="parse_boolean",
        )

    # Datetime / date / time patterns.
    for pat in _DATE_PATTERNS:
        if _all_match(sub, pat, sample_size):
            return InferredType(
                name="date",
                confidence=0.92,
                pandas_dtype=str(series.dtype),
                transform="parse_date",
                detected_pattern=pat.pattern,
            )

    if _majority_match(sub, _TR_TIME_HHMM, sample_size):
        return InferredType(
            name="time",
            confidence=0.9,
            pandas_dtype=str(series.dtype),
            transform="parse_time",
        )

    # Currency: detect symbol then strip it.
    sym_match = re.compile(
        r"(?P<sym>[$€£¥₺]|TRY|USD|EUR|GBP|JPY|RUB)"
    )

    def _looks_like_currency() -> Tuple[bool, Optional[str]]:
        # Match at least 50% of samples.
        hits = [re.search(sym_match, s) for s in cleaned_samples]
        syms = [h.group("sym") for h in hits if h]
        if not syms:
            return False, None
        if len(syms) / max(len(cleaned_samples), 1) < 0.5:
            return False, None
        # Most-common currency across hits.
        from collections import Counter  # noqa: E402, F401

        most_common, _ = Counter(syms).most_common(1)[0]
        return True, most_common

    is_currency, currency = _looks_like_currency()
    if is_currency:
        return InferredType(
            name="currency",
            confidence=0.9,
            pandas_dtype=str(series.dtype),
            transform="parse_currency",
            detected_currency=currency,
        )

    if _majority_match(sub, _PERCENT_RE, sample_size):
        return InferredType(
            name="percent",
            confidence=0.9,
            pandas_dtype=str(series.dtype),
            transform="parse_percent",
        )

    # If the column has very few unique values relative to n,
    # infer a categorical (low cardinality).
    unique_ratio = sub.nunique() / max(n, 1)
    if unique_ratio < 0.05 and sub.nunique() <= 50:
        return InferredType(
            name="categorical",
            confidence=0.85,
            pandas_dtype=str(series.dtype),
            transform="cast_string",
        )

    return InferredType(
        name="string",
        confidence=0.7,
        pandas_dtype=str(series.dtype),
        transform="cast_string",
    )


# ---------------------------------------------------------------------------
# Schema container
# ---------------------------------------------------------------------------


@dataclass
class ColumnInference:
    source: str
    inferred: InferredType

    def to_dict(self) -> Dict[str, Any]:
        return {"source": self.source, "inferred": self.inferred.to_dict()}


@dataclass
class Schema:
    columns: List[ColumnInference] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"columns": [c.to_dict() for c in self.columns]}

    def column_names(self) -> List[str]:
        return [c.source for c in self.columns]


def infer_schema(df: pd.DataFrame, *, sample: int = 10000) -> Schema:
    """Infer a Schema for every column in ``df``."""
    schema = Schema(columns=[])
    for col in df.columns:
        if isinstance(col, str) and col.startswith("__"):
            continue
        try:
            schema.columns.append(
                ColumnInference(
                    source=str(col),
                    inferred=infer_column_type(df[col], sample=sample),
                )
            )
        except Exception:
            schema.columns.append(
                ColumnInference(
                    source=str(col),
                    inferred=InferredType(
                        name="string",
                        confidence=0.0,
                        pandas_dtype=str(df[col].dtype),
                        transform="cast_string",
                    ),
                )
            )
    return schema


# ---------------------------------------------------------------------------
# Mapping to target schema
# ---------------------------------------------------------------------------


@dataclass
class ColumnMapping:
    source: str
    target: Optional[str]
    inferred_type: str
    confidence: float
    transform: str
    status: str  # "auto" | "review" | "unmapped"
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "inferred_type": self.inferred_type,
            "confidence": float(self.confidence),
            "transform": self.transform,
            "status": self.status,
            "rationale": self.rationale,
        }


@dataclass
class MappingResult:
    columns: List[ColumnMapping] = field(default_factory=list)
    unmapped_source: List[str] = field(default_factory=list)
    unfilled_target: List[str] = field(default_factory=list)
    min_confidence_auto_apply: float = 0.9
    auto_apply_count: int = 0
    review_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "columns": [c.to_dict() for c in self.columns],
            "unmapped_source": list(self.unmapped_source),
            "unfilled_target": list(self.unfilled_target),
            "min_confidence_auto_apply": self.min_confidence_auto_apply,
            "auto_apply_count": self.auto_apply_count,
            "review_count": self.review_count,
        }


def _normalise_name(s: str) -> str:
    n = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in n if not unicodedata.combining(c))


_TYPE_COMPATIBLE: Dict[str, set] = {
    "integer": {"integer", "float", "id"},
    "float": {"integer", "float", "percent", "currency"},
    "string": {"string", "categorical"},
    "categorical": {"string", "categorical", "boolean"},
    "boolean": {"boolean", "categorical"},
    "date": {"date", "datetime"},
    "datetime": {"datetime", "date"},
    "time": {"time"},
    "percent": {"float", "percent"},
    "currency": {"float", "currency"},
    "id": {"integer", "id"},
}


def _name_score(source_norm: str, target_norm: str) -> float:
    """Levenshtein-style normalised similarity score in [0, 1]."""
    if source_norm == target_norm:
        return 1.0
    if not source_norm or not target_norm:
        return 0.0
    # Token overlap.
    s_tokens = set(_split_tokens(source_norm))
    t_tokens = set(_split_tokens(target_norm))
    if s_tokens & t_tokens:
        # Jaccard on tokens.
        inter = len(s_tokens & t_tokens)
        union = len(s_tokens | t_tokens)
        token_score = inter / union
    else:
        token_score = 0.0
    # Character n-gram overlap (bigrams).
    s_bigrams = {source_norm[i : i + 2] for i in range(len(source_norm) - 1)}
    t_bigrams = {target_norm[i : i + 2] for i in range(len(target_norm) - 1)}
    if s_bigrams and t_bigrams:
        bg_score = len(s_bigrams & t_bigrams) / max(len(s_bigrams | t_bigrams), 1)
    else:
        bg_score = 0.0
    # Substring match (e.g. "id" in "customer_id").
    sub_score = 0.0
    if source_norm in target_norm or target_norm in source_norm:
        shorter = min(len(source_norm), len(target_norm))
        longer = max(len(source_norm), len(target_norm))
        sub_score = shorter / longer
    # Weighted blend.
    return 0.4 * token_score + 0.4 * bg_score + 0.2 * sub_score


def _split_tokens(name_norm: str) -> List[str]:
    parts = re.split(r"[_\s.\-:]+", name_norm)
    return [p for p in parts if p]


def _best_match(source_name: str, inferred_name: str, target_schema: Schema) -> Tuple[Optional[Tuple[ColumnInference, float]], List[Tuple[ColumnInference, float]]]:
    """Pick the best target column for ``source_name``.

    Returns ``(chosen, ranked)`` where ``chosen`` is the top candidate
    above the implicit 0.0 cutoff or ``None`` if no candidate clears
    a small lexical-match floor.
    """
    src_norm = _normalise_name(source_name)
    candidates: List[Tuple[ColumnInference, float]] = []
    for tcol in target_schema.columns:
        tgt_norm = _normalise_name(tcol.source)
        name_score = _name_score(src_norm, tgt_norm)
        # Type compatibility bonus.
        if inferred_name in _TYPE_COMPATIBLE.get(tcol.inferred.name, set()):
            type_bonus = 0.15
        elif tcol.inferred.name in _TYPE_COMPATIBLE.get(inferred_name, set()):
            type_bonus = 0.05
        else:
            type_bonus = 0.0
        score = min(name_score + type_bonus, 1.0)
        candidates.append((tcol, score))

    candidates.sort(key=lambda x: x[1], reverse=True)
    if candidates and candidates[0][1] >= 0.3:
        return candidates[0], candidates
    return None, candidates


def build_mapping(
    source: Schema,
    target: Schema,
    *,
    corrections: Optional[Mapping[str, str]] = None,
    min_confidence_auto_apply: float = 0.9,
) -> MappingResult:
    """Match ``source`` columns to ``target`` columns.

    ``corrections`` is a {source_col: target_col} dict supplied by the
    user; these mappings win outright (deterministic, no score).
    Otherwise the top lexical+type candidate above 0.7 wins.
    Confidence < 0.7 → status ``review`` (HITL queue).
    """
    corrections = corrections or {}
    used_targets = set()
    result = MappingResult(min_confidence_auto_apply=min_confidence_auto_apply)
    for s_col in source.columns:
        target_col_name = corrections.get(s_col.source)
        if target_col_name is not None:
            # Force-match if target column exists.
            match = next(
                (t for t in target.columns if t.source == target_col_name),
                None,
            )
            if match is not None:
                used_targets.add(target_col_name)
                result.columns.append(
                    ColumnMapping(
                        source=s_col.source,
                        target=target_col_name,
                        inferred_type=s_col.inferred.name,
                        confidence=1.0,
                        transform=s_col.inferred.transform,
                        status="auto",
                        rationale="user-correction",
                    )
                )
                result.auto_apply_count += 1
                continue
        chosen, ranked = _best_match(
            s_col.source, s_col.inferred.name, target
        )
        if chosen is None:
            result.unmapped_source.append(s_col.source)
            result.columns.append(
                ColumnMapping(
                    source=s_col.source,
                    target=None,
                    inferred_type=s_col.inferred.name,
                    confidence=0.0,
                    transform="drop",
                    status="unmapped",
                )
            )
            continue
        target_col, score = chosen
        status = "auto" if score >= min_confidence_auto_apply else "review"
        if target_col.source in used_targets:
            status = "review"
            score = min(score, 0.5)
        else:
            used_targets.add(target_col.source)
        if status == "auto":
            result.auto_apply_count += 1
        else:
            result.review_count += 1
        rationale = "; ".join(
            f"candidate={t.source} score={round(s, 3)}"
            for t, s in ranked[:3]
        )
        result.columns.append(
            ColumnMapping(
                source=s_col.source,
                target=target_col.source,
                inferred_type=s_col.inferred.name,
                confidence=round(float(score), 4),
                transform=s_col.inferred.transform,
                status=status,
                rationale=rationale,
            )
        )
    # Targets that no source filled.
    filled_targets = {
        c.target for c in result.columns if c.target is not None
    }
    result.unfilled_target = sorted(
        t.source for t in target.columns if t.source not in filled_targets
    )
    return result


def mapping_summary(mapping: MappingResult) -> Dict[str, Any]:
    """Flat dict for downstream I/O consumers (I2 catalog, etc.)."""
    return {
        "n_columns": len(mapping.columns),
        "n_auto": mapping.auto_apply_count,
        "n_review": mapping.review_count,
        "unmapped_source": mapping.unmapped_source,
        "unfilled_target": mapping.unfilled_target,
        "min_confidence_auto_apply": mapping.min_confidence_auto_apply,
        "columns": [c.to_dict() for c in mapping.columns],
    }


__all__ = [
    "InferredType",
    "ColumnInference",
    "Schema",
    "infer_column_type",
    "infer_schema",
    "ColumnMapping",
    "MappingResult",
    "build_mapping",
    "mapping_summary",
]


