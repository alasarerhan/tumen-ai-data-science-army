from __future__ import annotations

"""d3_feature_store. Deterministic feature-store tools. Implements
D3 — versioned feature definitions (name + dtype + transform +
owner + tags), online/offline consistency check, freshness probe
(last-update timestamps + staleness flag), search/catalog query,
and lineage pointers to J12 nodes.
"""

import time  # noqa: E402, F401
import uuid  # noqa: E402, F401
from dataclasses import dataclass, field  # noqa: E402, F401
from typing import Any, Dict, List, Optional, Sequence, Tuple  # noqa: E402, F401

VALID_DTYPES = {"int", "float", "string", "bool", "array", "embed"}


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> float:
    return time.time()


# ----- Feature definition --------------------------------------------------


@dataclass
class FeatureDefinition:
    feature_id: str
    name: str
    version: str
    dtype: str
    transform: str
    owner: str
    tags: List[str]
    created_at: float
    lineage_node_id: Optional[str] = None
    description: str = ""


@dataclass
class FeatureStore:
    definitions: List[FeatureDefinition] = field(default_factory=list)

    def add(self, d: FeatureDefinition) -> None:
        self.definitions.append(d)

    def by_id(self, fid: str) -> Optional[FeatureDefinition]:
        return next((d for d in self.definitions if d.feature_id == fid), None)

    def by_name(self, name: str) -> List[FeatureDefinition]:
        return [d for d in self.definitions if d.name == name]


def register_feature(
    store: FeatureStore,
    *,
    name: str,
    dtype: str,
    transform: str,
    owner: str,
    version: str = "1.0.0",
    tags: Optional[Sequence[str]] = None,
    description: str = "",
    lineage_node_id: Optional[str] = None,
    feature_id: Optional[str] = None,
) -> FeatureDefinition:
    if dtype not in VALID_DTYPES:
        raise ValueError(f"dtype must be one of {sorted(VALID_DTYPES)}")
    d = FeatureDefinition(
        feature_id=feature_id or _new_id(),
        name=name,
        version=version,
        dtype=dtype,
        transform=transform,
        owner=owner,
        tags=list(tags or []),
        created_at=_now(),
        lineage_node_id=lineage_node_id,
        description=description,
    )
    store.add(d)
    return d


# ----- Search / catalog ----------------------------------------------------


def search_features(
    store: FeatureStore,
    *,
    query: Optional[str] = None,
    tag: Optional[str] = None,
    owner: Optional[str] = None,
    dtype: Optional[str] = None,
    limit: int = 50,
) -> List[FeatureDefinition]:
    out = list(store.definitions)
    if query is not None:
        q = query.lower()
        out = [d for d in out if q in d.name.lower() or q in d.description.lower()]
    if tag is not None:
        out = [d for d in out if tag in d.tags]
    if owner is not None:
        out = [d for d in out if d.owner == owner]
    if dtype is not None:
        out = [d for d in out if d.dtype == dtype]
    return out[:limit]


# ----- Versioning helpers --------------------------------------------------


def version_sort_key(version: str) -> Tuple[int, ...]:
    parts: List[int] = []
    for piece in version.split("."):
        try:
            parts.append(int(piece))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def latest_version(
    store: FeatureStore,
    name: str,
) -> Optional[FeatureDefinition]:
    same = store.by_name(name)
    if not same:
        return None
    return max(same, key=lambda d: version_sort_key(d.version))


# ----- Online / offline consistency ---------------------------------------


@dataclass
class ConsistencyReport:
    feature_id: str
    online_dtype: Optional[str]
    offline_dtype: Optional[str]
    online_value_sample: List[Any]
    offline_value_sample: List[Any]
    dtypes_match: bool
    samples_match: bool
    consistent: bool
    issues: List[str]


def _sample_match(
    online: Sequence[Any],
    offline: Sequence[Any],
    tolerance: float = 1e-9,
) -> bool:
    if len(online) != len(offline):
        return False
    for a, b in zip(online, offline):
        try:
            if abs(float(a) - float(b)) > tolerance:
                return False
        except (TypeError, ValueError):
            if str(a) != str(b):
                return False
    return True


def check_consistency(
    *,
    feature_id: str,
    online_dtype: Optional[str],
    offline_dtype: Optional[str],
    online_value_sample: Sequence[Any],
    offline_value_sample: Sequence[Any],
    feature_name: Optional[str] = None,
) -> ConsistencyReport:
    issues: List[str] = []
    dtypes_match = (
        online_dtype is not None and offline_dtype is not None and online_dtype == offline_dtype
    )
    if not dtypes_match:
        issues.append(f"dtype mismatch: online={online_dtype!r} offline={offline_dtype!r}")
    samples_match = _sample_match(online_value_sample, offline_value_sample)
    if not samples_match:
        issues.append("value sample mismatch between online and offline")
    return ConsistencyReport(
        feature_id=feature_id,
        online_dtype=online_dtype,
        offline_dtype=offline_dtype,
        online_value_sample=list(online_value_sample),
        offline_value_sample=list(offline_value_sample),
        dtypes_match=dtypes_match,
        samples_match=samples_match,
        consistent=(dtypes_match and samples_match),
        issues=issues,
    )


# ----- Freshness probe -----------------------------------------------------


@dataclass
class FreshnessRecord:
    feature_id: str
    last_updated_at: float
    freshness_sla_seconds: float


@dataclass
class FreshnessReport:
    feature_id: str
    age_seconds: float
    sla_seconds: float
    is_stale: bool
    observed_at: float


def probe_freshness(
    record: FreshnessRecord,
    *,
    now: Optional[float] = None,
) -> FreshnessReport:
    ts = now if now is not None else _now()
    age = ts - record.last_updated_at
    return FreshnessReport(
        feature_id=record.feature_id,
        age_seconds=float(age),
        sla_seconds=float(record.freshness_sla_seconds),
        is_stale=age > record.freshness_sla_seconds,
        observed_at=ts,
    )


def bulk_probe_freshness(
    records: Sequence[FreshnessRecord],
    *,
    now: Optional[float] = None,
) -> List[FreshnessReport]:
    return [probe_freshness(r, now=now) for r in records]


# ----- Lineage pointer -----------------------------------------------------


def attach_lineage(
    store: FeatureStore,
    *,
    feature_id: str,
    lineage_node_id: str,
) -> FeatureDefinition:
    d = store.by_id(feature_id)
    if d is None:
        raise KeyError(f"feature_id not found: {feature_id}")
    d.lineage_node_id = lineage_node_id
    return d


# ----- Catalog payload -----------------------------------------------------


def catalog_payload(
    store: FeatureStore,
    feature_ids: Sequence[str],
) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for fid in feature_ids:
        d = store.by_id(fid)
        if d is None:
            continue
        items.append(
            {
                "feature_id": d.feature_id,
                "name": d.name,
                "version": d.version,
                "dtype": d.dtype,
                "owner": d.owner,
                "tags": d.tags,
                "lineage_node_id": d.lineage_node_id,
                "description": d.description,
                "created_at": d.created_at,
            }
        )
    return {
        "n": len(items),
        "features": items,
    }
