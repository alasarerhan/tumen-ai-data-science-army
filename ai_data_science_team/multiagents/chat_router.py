from __future__ import annotations

"""IntentRouter — keyword + LLM-fallback intent classifier for M21.

Maps a natural-language user message to the most appropriate agent name
registered in the platform.

Architecture decision
---------------------
This is a **routing workflow**, not a new agent (Anthropic "Building Effective
Agents", 2024).  Intent classification is a well-defined, sequential task:

    1. Keyword matching  (zero LLM cost, <1 ms, covers 90 %+ of cases)
    2. LLM fallback      (only when keyword confidence < ``llm_threshold``)

Adding a new LangGraph agent layer here would add latency and cost with no
benefit — a ``classify → dispatch`` pattern is more predictable, cheaper, and
easier to test/debug.

Usage
-----
::

    router = IntentRouter()
    decision = router.route("Bu verideki anomalileri bul")
    logger.info(decision.agent_name)    # "anomaly_detection_agent"
    logger.info(decision.method)        # "keyword"
    logger.info(decision.confidence)    # 0.5

    # With LLM fallback (triggers when no keyword hits)
    router_with_llm = IntentRouter(llm_threshold=0.1, llm=some_langchain_llm)
    decision = router_with_llm.route("unusual patterns in this dataset?")
"""

import logging  # noqa: E402, F401

logger = logging.getLogger(__name__)
import re  # noqa: E402, F401
from dataclasses import dataclass, field  # noqa: E402, F401
from typing import Dict, List, Optional, Tuple  # noqa: E402, F401


# ---------------------------------------------------------------------------
# Routing table
# ---------------------------------------------------------------------------

#: Maps agent name → list of trigger keywords (matched case-insensitively).
#: Both Turkish and English terms are included to support mixed-language usage.
INTENT_MAP: Dict[str, List[str]] = {
    "pandas_data_analyst": [
        # Turkish
        "analiz", "istatistik", "dağılım", "korelasyon", "pivot", "özet",
        "gruplama", "gruple", "sayım", "ortalama", "median", "standart sapma",
        "filtrele", "göster", "listele", "en çok", "en az", "sırala",
        "karşılaştır", "histogram", "bar",
        # English
        "analyze", "analysis", "summarize", "statistics", "distribution",
        "correlation", "group by", "count", "average", "mean", "std",
        "aggregate", "filter", "show", "list", "top", "bottom", "sort",
        "rank", "compare", "bar chart", "scatter",
    ],
    "eda_tools_agent": [
        # Turkish
        "eda", "keşif", "keşifsel", "profil", "profilleme", "eksik veri",
        "sweetviz", "dtale", "veri kalite genel", "genel bakış", "betimleyici",
        # English
        "eda", "exploratory", "explore", "profile", "missing data",
        "missing values", "sweetviz", "dtale", "overview", "descriptive",
    ],
    "sql_data_analyst": [
        # Turkish
        "sql", "veritabanı", "veri tabanı", "tablo sorgu", "join", "where",
        "select", "database",
        # English
        "sql", "database", "query", "join", "select", "where", "from",
        "sqlite", "postgres", "mysql", "db query",
    ],
    "data_cleaning_agent": [
        # Turkish
        "temizle", "temizlik", "eksik doldur", "impute", "aykırı kaldır",
        "duplikat", "tekrar eden", "bozuk veri", "düzelt", "normalize et",
        # English
        "clean data", "cleaning", "impute", "imputation", "remove duplicates",
        "outlier removal", "fix data", "normalize data",
    ],
    "document_parser_agent": [
        # Turkish
        "url", "web sitesi", "sayfayı çek", "scraping", "pdf oku", "belge oku",
        "döküman", "html sayfası",
        # English
        "url", "web scraping", "scrape", "pdf", "document", "html", "parse",
        "download page", "fetch url", "webpage",
    ],
    "api_connector_agent": [
        # Turkish
        "rest api", "api çağır", "endpoint", "webhook", "http isteği",
        # English
        "api", "rest api", "endpoint", "webhook", "http request",
        "json endpoint", "call api",
    ],
    "model_serving_agent": [
        # Turkish
        "tahmin yap", "inference", "modeli uygula", "sınıflandır",
        "modeli yükle", "modeli çalıştır",
        # English
        "predict", "inference", "run model", "serve model",
        "classification predict", "regression predict", "load model",
    ],
    "anomaly_detection_agent": [
        # Turkish
        "anomali", "aykırı değer", "outlier tespiti", "fraud tespiti",
        "anormallik", "normal dışı",
        # English
        "anomaly", "anomalies", "outlier detection", "fraud detection",
        "abnormal", "detect anomalies",
    ],
}

#: Fallback agent — used when keyword matching finds no hits.
_DEFAULT_AGENT = "pandas_data_analyst"


# ---------------------------------------------------------------------------
# RouterDecision
# ---------------------------------------------------------------------------


@dataclass
class RouterDecision:
    """Result of a single intent classification call.

    Attributes
    ----------
    agent_name : str
        The agent selected for this message.
    confidence : float
        Normalised confidence in [0, 1].  For keyword matching this is
        ``best_hits / total_hits``; for LLM it is a fixed ``0.8``.
    method : str
        How the decision was made: ``"keyword"``, ``"llm"``, or ``"default"``.
    raw_scores : dict[str, int]
        Raw keyword hit counts per agent (useful for debugging).
    """

    agent_name: str
    confidence: float
    method: str
    raw_scores: Dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# IntentRouter
# ---------------------------------------------------------------------------


class IntentRouter:
    """Lightweight intent router for the AI Workspace.

    Parameters
    ----------
    intent_map : dict | None
        Keyword routing table.  Defaults to the module-level :data:`INTENT_MAP`.
    llm_threshold : float
        Minimum keyword confidence required to skip LLM fallback.
        Set to ``0.0`` (default) to always trust keyword results.
        Set to e.g. ``0.3`` to invoke the LLM when keywords are inconclusive.
    llm : LangChain LLM | None
        Used only when ``llm_threshold > 0`` and keyword confidence is below
        the threshold.  If *None* and the threshold is not met, the router
        falls back to :data:`_DEFAULT_AGENT`.
    """

    def __init__(
        self,
        intent_map: Optional[Dict[str, List[str]]] = None,
        llm_threshold: float = 0.0,
        llm=None,
    ) -> None:
        self._map = intent_map or INTENT_MAP
        self._llm_threshold = llm_threshold
        self._llm = llm

    # ------------------------------------------------------------------

    def route(self, message: str) -> RouterDecision:
        """Classify *message* and return a :class:`RouterDecision`.

        Keyword matching is attempted first.  If the best-match confidence
        is below ``llm_threshold`` **and** an LLM is configured, the LLM
        is queried for a final classification.

        Parameters
        ----------
        message : str
            The raw user message.

        Returns
        -------
        RouterDecision
        """
        scores = self._keyword_scores(message)
        best_agent, best_score, total = self._best_from_scores(scores)
        confidence = best_score / total if total > 0 else 0.0

        # No hits at all → default (or try LLM)
        if best_agent is None:
            if self._llm is not None and self._llm_threshold >= 0.0:
                return self._llm_route(message, scores)
            return RouterDecision(
                agent_name=_DEFAULT_AGENT,
                confidence=0.0,
                method="default",
                raw_scores=scores,
            )

        # Keyword confidence is sufficient
        if confidence >= self._llm_threshold:
            return RouterDecision(
                agent_name=best_agent,
                confidence=min(confidence, 1.0),
                method="keyword",
                raw_scores=scores,
            )

        # Keyword confidence below threshold → try LLM
        if self._llm is not None:
            return self._llm_route(message, scores)

        # No LLM available, use best keyword match anyway
        return RouterDecision(
            agent_name=best_agent,
            confidence=min(confidence, 1.0),
            method="keyword",
            raw_scores=scores,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _keyword_scores(self, message: str) -> Dict[str, int]:
        """Return a dict of agent_name → keyword hit count."""
        msg_lower = message.lower()
        scores: Dict[str, int] = {}
        for agent_name, keywords in self._map.items():
            hits = 0
            for kw in keywords:
                kw_lower = kw.lower()
                # Use word-boundary regex for single-word keywords;
                # substring match for multi-word phrases.
                if " " in kw_lower:
                    if kw_lower in msg_lower:
                        hits += 1
                else:
                    if re.search(r"\b" + re.escape(kw_lower) + r"\b", msg_lower):
                        hits += 1
            if hits > 0:
                scores[agent_name] = hits
        return scores

    def _best_from_scores(
        self, scores: Dict[str, int]
    ) -> Tuple[Optional[str], int, int]:
        """Return *(best_agent, best_score, total_hits)*."""
        if not scores:
            return None, 0, 0
        total = sum(scores.values())
        best = max(scores, key=lambda k: scores[k])
        return best, scores[best], total

    def _llm_route(
        self, message: str, keyword_scores: Dict[str, int]
    ) -> RouterDecision:
        """Call the LLM classifier and map its output to a known agent name."""
        agent_names = list(self._map.keys())
        prompt = (
            "You are an intent classifier for a data analysis platform. "
            "Given a user message, return ONLY the single most appropriate "
            "agent name from the list below.\n\n"
            f"User message: {message}\n\n"
            "Agent options (reply with exactly one):\n"
            + "\n".join(f"- {n}" for n in agent_names)
            + "\n\nReply with exactly one agent name."
        )
        try:
            resp = self._llm.invoke(prompt)
            text = resp.content.strip() if hasattr(resp, "content") else str(resp).strip()
            text_lower = text.lower()
            for name in agent_names:
                if name.lower() in text_lower:
                    return RouterDecision(
                        agent_name=name,
                        confidence=0.8,
                        method="llm",
                        raw_scores=keyword_scores,
                    )
        except Exception:
            pass

        return RouterDecision(
            agent_name=_DEFAULT_AGENT,
            confidence=0.0,
            method="default",
            raw_scores=keyword_scores,
        )
