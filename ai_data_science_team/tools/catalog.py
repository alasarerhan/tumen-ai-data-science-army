from __future__ import annotations

"""
i2_catalog
=========

Deterministic data-catalog + semantic-layer tools supporting
**I2 — Data Catalog & Semantik Katman** (spec
``docs/specs/I2-data-catalog.md``).

The agent layer (LLM-driven column descriptions, embedding-based
search) lives in ``agents/catalog_scanner_agent.py``. This module
ships the deterministic core: catalog tree, scan ingestion,
semantic index (lexical + synonym), search and resolve APIs.

Public surface
--------------

* :func:`add_source` — register a source (database / table / columns).
* :func:`attach_profile` — fold a ``profile_dataframe`` result
  (B1) onto the source's column stats.
* :func:`add_pii_badges` — fold a ``scan_pii`` result (B5) onto the
  source's columns.
* :func:`catalog_tree` — return the source→table→column tree the
  I2 UI renders.
* :func:`add_term` / :func:`bind_term_column` — business-term ↔
  column mapping.
* :func:`search` — fuzzy lexical search across terms, column
  names, descriptions; synonym table included.
* :func:`resolve_data(term)` — the I1 planner's call: given a
  NL term return the top matching source.column candidates.
* :func:`record_lineage` — minimal "who uses what" lineage.
"""

import unicodedata  # noqa: E402, F401
from dataclasses import dataclass, field  # noqa: E402, F401
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple  # noqa: E402, F401

# ---------------------------------------------------------------------------
# Default synonym table — Turkish / English business-term aliases.
# ---------------------------------------------------------------------------


DEFAULT_SYNONYMS: Dict[str, List[str]] = {
    "churn": [
        "müşteri kaybı",
        "müşteri kayip",
        "churn rate",
        "kayip orani",
        "abonelik iptali",
        "attrition",
        "kayip",
    ],
    "revenue": [
        "ciro",
        "gelir",
        "hasılat",
        "kazanç",
        "income",
        "sales",
        "amount",
        "tutar",
        "price",
        "fiyat",
    ],
    "customer": [
        "müşteri",
        "kullanıcı",
        "user",
        "client",
        "member",
    ],
    "transaction": [
        "işlem",
        "transaction",
        "satış",
        "sipariş",
        "order",
    ],
    "session": [
        "oturum",
        "session",
        "ziyaret",
        "visit",
    ],
    "churn_rate": [
        "churn rate",
        "kayip orani",
        "abandonment rate",
        "kayip oranı",
    ],
    "ltv": [
        "lifetime value",
        "yaşamboyu değer",
        "müşteri değeri",
    ],
}


# ---------------------------------------------------------------------------
# Source / column records
# ---------------------------------------------------------------------------


@dataclass
class ColumnEntry:
    name: str
    dtype: str = "object"
    description: Optional[str] = None
    pii: Dict[str, Any] = field(default_factory=dict)
    stats: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "dtype": self.dtype,
            "description": self.description,
            "pii": dict(self.pii),
            "stats": dict(self.stats),
        }


@dataclass
class TableEntry:
    name: str
    columns: List[ColumnEntry] = field(default_factory=list)
    description: Optional[str] = None

    def column_names(self) -> List[str]:
        return [c.name for c in self.columns]

    def get_column(self, name: str) -> Optional[ColumnEntry]:
        for c in self.columns:
            if c.name == name:
                return c
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "columns": [c.to_dict() for c in self.columns],
        }


@dataclass
class SourceEntry:
    name: str
    kind: str  # "snowflake" | "postgres" | "csv" | "sheets" | "object_storage"
    tables: List[TableEntry] = field(default_factory=list)
    description: Optional[str] = None

    def get_table(self, name: str) -> Optional[TableEntry]:
        for t in self.tables:
            if t.name == name:
                return t
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "description": self.description,
            "tables": [t.to_dict() for t in self.tables],
        }


@dataclass
class Catalog:
    sources: List[SourceEntry] = field(default_factory=list)
    terms: Dict[str, List[str]] = field(default_factory=dict)  # term → column refs
    lineage: List[Dict[str, str]] = field(default_factory=list)
    synonym_table: Dict[str, List[str]] = field(
        default_factory=lambda: {k: list(v) for k, v in DEFAULT_SYNONYMS.items()}
    )

    def find_source(self, name: str) -> Optional[SourceEntry]:
        for s in self.sources:
            if s.name == name:
                return s
        return None


# ---------------------------------------------------------------------------
# Source registration
# ---------------------------------------------------------------------------


def add_source(
    catalog: Catalog,
    *,
    name: str,
    kind: str,
    tables: Optional[Sequence[Mapping[str, Any]]] = None,
    description: Optional[str] = None,
) -> SourceEntry:
    """Register a new source and return the entry."""
    src = SourceEntry(name=name, kind=kind, description=description)
    for t in tables or []:
        cols: List[ColumnEntry] = []
        for col in t.get("columns", []) or []:
            if isinstance(col, str):
                cols.append(ColumnEntry(name=col))
            elif isinstance(col, Mapping):
                cols.append(
                    ColumnEntry(
                        name=str(col.get("name", "")),
                        dtype=str(col.get("dtype", "object")),
                        description=col.get("description"),
                    )
                )
        src.tables.append(
            TableEntry(
                name=str(t.get("name", "")),
                description=t.get("description"),
                columns=cols,
            )
        )
    catalog.sources.append(src)
    return src


def add_table(
    catalog: Catalog,
    source_name: str,
    table_name: str,
    columns: Sequence[Mapping[str, Any]],
    description: Optional[str] = None,
) -> Optional[TableEntry]:
    """Append a new table to an existing source."""
    src = catalog.find_source(source_name)
    if src is None:
        return None
    cols = [
        ColumnEntry(
            name=str(c.get("name", "")),
            dtype=str(c.get("dtype", "object")),
            description=c.get("description"),
        )
        for c in columns
    ]
    t = TableEntry(name=table_name, description=description, columns=cols)
    src.tables.append(t)
    return t


# ---------------------------------------------------------------------------
# Profile + PII badge inheritance
# ---------------------------------------------------------------------------


def attach_profile(catalog: Catalog, source_name: str, profile: Mapping[str, Any]) -> None:
    """Fold a ``profile_dataframe`` (B1) result onto ``source_name``.

    The first table in the source is treated as the profiled table.
    """
    src = catalog.find_source(source_name)
    if src is None or not src.tables:
        return
    table = src.tables[0]
    name_to_idx = {c.name: i for i, c in enumerate(table.columns)}
    for col in profile.get("columns", []) or []:
        col_name = col.get("name")
        if col_name is None:
            continue
        if col_name in name_to_idx:
            # Update existing column.
            table.columns[name_to_idx[col_name]].stats = dict(
                {k: v for k, v in col.items() if k not in {"name", "pii"}}
            )
        else:
            # Add as new column (B1's column stats only).
            table.columns.append(
                ColumnEntry(
                    name=str(col_name),
                    dtype=str(col.get("dtype", "object")),
                    stats={k: v for k, v in col.items() if k not in {"name", "pii"}},
                )
            )


def add_pii_badges(catalog: Catalog, source_name: str, pii_scan: Mapping[str, Any]) -> None:
    """Fold a ``scan_pii`` (B5) result onto ``source_name``.

    Updates ``column.pii`` with the per-column PII signal.
    """
    src = catalog.find_source(source_name)
    if src is None or not src.tables:
        return
    table = src.tables[0]
    name_to_idx = {c.name: i for i, c in enumerate(table.columns)}
    for finding in pii_scan.get("findings", []) or []:
        col_name = finding.get("column")
        if col_name is None or col_name not in name_to_idx:
            continue
        idx = name_to_idx[col_name]
        table.columns[idx].pii = {
            "signal": finding.get("pii_signal", "low"),
            "kind": finding.get("pii_kind"),
            "match_ratio": finding.get("match_ratio", 0.0),
        }


# ---------------------------------------------------------------------------
# Tree projection
# ---------------------------------------------------------------------------


def catalog_tree(catalog: Catalog) -> Dict[str, Any]:
    """Return the source → table → column tree for the I2 UI."""
    return {
        "sources": [s.to_dict() for s in catalog.sources],
        "n_sources": len(catalog.sources),
        "n_tables": sum(len(s.tables) for s in catalog.sources),
        "n_columns": sum(len(t.columns) for s in catalog.sources for t in s.tables),
    }


# ---------------------------------------------------------------------------
# Term ↔ column mapping
# ---------------------------------------------------------------------------


def add_term(catalog: Catalog, term: str, *, synonyms: Optional[Sequence[str]] = None) -> None:
    """Register a business term; optionally add synonyms."""
    catalog.terms.setdefault(term, [])
    if synonyms:
        for s in synonyms:
            if s not in catalog.terms[term]:
                catalog.terms[term].append(s)


def bind_term_column(
    catalog: Catalog,
    term: str,
    *,
    source: str,
    table: str,
    column: str,
    confidence: float = 0.7,
) -> bool:
    """Link a term to a specific source.table.column.

    ``confidence`` is consumed by :func:`search` and :func:`resolve_data`.
    Source names with dots are preserved by encoding the bound ref
    as ``source::table::column@confidence``.
    """
    src = catalog.find_source(source)
    if src is None:
        return False
    t = src.get_table(table)
    if t is None or t.get_column(column) is None:
        return False
    catalog.terms.setdefault(term, []).append(f"{source}::{table}::{column}@{confidence}")
    return True


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def _normalise(s: str) -> str:
    n = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in n if not unicodedata.combining(c))


def _match_score(query_norm: str, target_norm: str) -> float:
    """Token + bigram + substring similarity in [0, 1]."""
    if not query_norm or not target_norm:
        return 0.0
    if query_norm in target_norm or target_norm in query_norm:
        return 1.0
    q_tokens = set(query_norm.split())
    t_tokens = set(target_norm.split())
    token_score = (
        len(q_tokens & t_tokens) / max(len(q_tokens | t_tokens), 1) if q_tokens or t_tokens else 0.0
    )
    q_bi = {query_norm[i : i + 2] for i in range(len(query_norm) - 1)}
    t_bi = {target_norm[i : i + 2] for i in range(len(target_norm) - 1)}
    bi_score = len(q_bi & t_bi) / max(len(q_bi | t_bi), 1) if q_bi and t_bi else 0.0
    return 0.5 * token_score + 0.5 * bi_score


@dataclass
class SearchHit:
    source: str
    table: str
    column: str
    score: float
    matched_term: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "table": self.table,
            "column": self.column,
            "score": float(self.score),
            "matched_term": self.matched_term,
        }


def _expand_query(query: str, catalog: Catalog) -> List[Tuple[str, float]]:
    """Return list of (term, boost) — includes the original query and
    any synonym-table lookups.

    The synonym table is matched bidirectionally: a query like
    "müşteri kaybı" finds the ``churn`` key (substring) and then
    emits each of ``churn``'s synonyms so the secondary
    ``_match_score`` pass can find ``churn_label.churned`` by
    token overlap.
    """
    out: List[Tuple[str, float]] = [(query, 1.0)]
    qn = _normalise(query)
    if not qn:
        return out

    def _add(entries: List[Tuple[str, float]], term: str, boost: float) -> None:
        if (term, boost) not in entries:
            entries.append((term, boost))

    # 1) Synonym table: match key tokens against the query, then
    #    emit the key + its synonyms.
    for key, synonyms in catalog.synonym_table.items():
        key_norm = _normalise(key)
        for s in synonyms:
            s_norm = _normalise(s)
            if s_norm in qn or qn in s_norm or key_norm in qn or qn in key_norm:
                _add(out, key, 0.85)
                for syn in synonyms:
                    _add(out, syn, 0.85)
                break
    # 2) Declared business terms + their synonyms (not column-refs).
    for term, refs in catalog.terms.items():
        if _normalise(term) in qn or qn in _normalise(term):
            for alias in refs:
                if "@" in alias:
                    continue
                _add(out, alias, 0.85)
    return out


def search(catalog: Catalog, query: str, *, top_k: int = 5) -> List[SearchHit]:
    """Search columns by query (term/description)."""
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    if not query.strip():
        return []
    queries = _expand_query(query, catalog)
    hits: List[SearchHit] = []
    for src in catalog.sources:
        for t in src.tables:
            for col in t.columns:
                # Score against column name + description.
                col_norm = _normalise(col.name)
                desc_norm = _normalise(col.description or "")
                best_term = ""
                best_score = 0.0
                for q, boost in queries:
                    qn = _normalise(q)
                    s1 = _match_score(qn, col_norm) * boost
                    s2 = _match_score(qn, desc_norm) * boost
                    s = max(s1, s2)
                    if s > best_score:
                        best_score = s
                        best_term = q
                if best_score >= 0.30:
                    hits.append(
                        SearchHit(
                            source=src.name,
                            table=t.name,
                            column=col.name,
                            score=best_score,
                            matched_term=best_term,
                        )
                    )
    # Surface direct term→column bindings verbatim.  The ref
    # string carries the user-supplied confidence in ``@<conf>``;
    # we propagate it without additional boost so the spec's
    # "kullanıcı override" path stays authoritative.
    for term, refs in catalog.terms.items():
        if _normalise(term) in _normalise(query):
            for ref in refs:
                if "@" not in ref:
                    continue
                path, conf = ref.rsplit("@", 1)
                parts = path.split("::")
                if len(parts) == 3:
                    s, t, c = parts
                    hits.append(
                        SearchHit(
                            source=s,
                            table=t,
                            column=c,
                            score=float(conf),
                            matched_term=term,
                        )
                    )
    hits.sort(key=lambda h: h.score, reverse=True)
    # Deduplicate by (source, table, column) keeping the highest.
    seen: set = set()
    out: List[SearchHit] = []
    for h in hits:
        key = (h.source, h.table, h.column)
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
        if len(out) >= top_k:
            break
    return out


def resolve_data(catalog: Catalog, term: str, *, top_k: int = 3) -> List[Dict[str, Any]]:
    """I1 planner entrypoint: NL term → top source.column candidates."""
    return [h.to_dict() for h in search(catalog, term, top_k=top_k)]


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------


def record_lineage(
    catalog: Catalog,
    *,
    pipeline_id: str,
    source_name: str,
    table: str,
) -> None:
    """Append a record indicating that ``pipeline_id`` consumes
    ``source_name.table``.
    """
    catalog.lineage.append(
        {
            "pipeline_id": pipeline_id,
            "source": source_name,
            "table": table,
        }
    )


def lineage_for(
    catalog: Catalog, source_name: str, table: Optional[str] = None
) -> List[Dict[str, str]]:
    """Return all lineage records that consume the given source (and table)."""
    out: List[Dict[str, str]] = []
    for r in catalog.lineage:
        if r["source"] != source_name:
            continue
        if table is not None and r["table"] != table:
            continue
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# Convenience constructor
# ---------------------------------------------------------------------------


def make_catalog() -> Catalog:
    return Catalog()


__all__ = [
    "DEFAULT_SYNONYMS",
    "ColumnEntry",
    "TableEntry",
    "SourceEntry",
    "Catalog",
    "SearchHit",
    "add_source",
    "add_table",
    "attach_profile",
    "add_pii_badges",
    "catalog_tree",
    "add_term",
    "bind_term_column",
    "search",
    "resolve_data",
    "record_lineage",
    "lineage_for",
    "make_catalog",
]
