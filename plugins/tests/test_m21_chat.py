"""TG1 / TG2 / TG3 — Tests for M21 AI Workspace (ChatSession, IntentRouter, ChatWorkspace).

Test Groups
-----------
TG1 – Unit tests, **no LLM required** (~34 tests):
    * ChatMessage / ChatSession dataclasses  (5 tests)
    * ChatSessionStore CRUD                  (12 tests)
    * IntentRouter keyword routing           (12 tests)
    * INTENT_MAP coverage check              (2 tests)
    * _extract_response helper               (3 tests)

TG2 – Integration tests, **real gpt-4o-mini**:
    * ChatWorkspace.chat() — pandas analyst  (2 tests)
    * ChatWorkspace.chat() — eda agent       (1 test)
    * History population after chat          (1 test)

TG3 – E2E sanity (~3 tests):
    * Import check (M21 symbols accessible)
    * ChatWorkspace is plain Python (NOT a BaseAgent subclass)
    * Full pipeline: create_session → upload → chat → get_history

Run all:
    pytest tests/test_m21_chat.py -v

TG1 only (no LLM):
    pytest tests/test_m21_chat.py -v -m "not integration and not e2e"

TG2 only:
    pytest tests/test_m21_chat.py -v -m integration
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict
from unittest.mock import MagicMock

import pandas as pd
import pytest
from langchain_core.messages import AIMessage

from ai_data_science_team.multiagents.chat_router import (
    _DEFAULT_AGENT,
    INTENT_MAP,
    IntentRouter,
    RouterDecision,
)
from ai_data_science_team.multiagents.chat_session import (
    ChatMessage,
    ChatSession,
    ChatSessionStore,
    MongoChatSessionStore,
)
from ai_data_science_team.multiagents.chat_workspace import (
    ChatResponse,
    ChatWorkspace,
    _extract_response,
)

# ---------------------------------------------------------------------------
# Markers / skip helpers
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.m21

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
skip_no_key = pytest.mark.skipif(
    not OPENAI_API_KEY,
    reason="OPENAI_API_KEY is not set — skipping LLM-dependent test",
)

langchain_openai = pytest.importorskip(
    "langchain_openai",
    reason="langchain_openai is not installed",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def small_df() -> pd.DataFrame:
    """A tiny DataFrame for testing."""
    return pd.DataFrame(
        {
            "product": ["Bike A", "Bike B", "Bike C"],
            "sales": [150, 230, 190],
            "region": ["North", "South", "East"],
        }
    )


@pytest.fixture()
def store() -> ChatSessionStore:
    return ChatSessionStore()


@pytest.fixture()
def router() -> IntentRouter:
    return IntentRouter()


# ---------------------------------------------------------------------------
# ═══════════════════════════════════════════════════════════════
# TG1 — Unit tests (no LLM)
# ═══════════════════════════════════════════════════════════════
# ---------------------------------------------------------------------------


class TestChatMessageDataclass:
    """ChatMessage dataclass behaviour."""

    def test_role_and_content(self):
        msg = ChatMessage(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"

    def test_defaults(self):
        msg = ChatMessage(role="assistant", content="hi")
        assert msg.artifact is None
        assert msg.agent_used is None
        assert isinstance(msg.timestamp, datetime)

    def test_timestamp_is_utc(self):
        msg = ChatMessage(role="user", content="test")
        assert msg.timestamp.tzinfo is not None

    def test_artifact_stored(self):
        art = {"type": "table", "records": [{"a": 1}]}
        msg = ChatMessage(role="assistant", content="here", artifact=art)
        assert msg.artifact == art

    def test_agent_used_stored(self):
        msg = ChatMessage(role="assistant", content="done", agent_used="eda_tools_agent")
        assert msg.agent_used == "eda_tools_agent"


class TestChatSession:
    """ChatSession dataclass."""

    def test_creation(self):
        s = ChatSession(session_id="abc123")
        assert s.session_id == "abc123"
        assert s.messages == []
        assert s.datasets == {}

    def test_created_at_is_utc(self):
        s = ChatSession(session_id="x")
        assert s.created_at.tzinfo is not None


class TestChatSessionStore:
    """ChatSessionStore CRUD operations."""

    def test_create_generates_uuid(self, store: ChatSessionStore):
        s = store.create()
        assert len(s.session_id) == 36  # UUID4 format

    def test_create_with_explicit_id(self, store: ChatSessionStore):
        s = store.create(session_id="sess-1")
        assert s.session_id == "sess-1"

    def test_get_existing(self, store: ChatSessionStore):
        s = store.create()
        assert store.get(s.session_id) is s

    def test_get_missing_returns_none(self, store: ChatSessionStore):
        assert store.get("nonexistent") is None

    def test_delete_existing_returns_true(self, store: ChatSessionStore):
        s = store.create()
        assert store.delete(s.session_id) is True
        assert store.get(s.session_id) is None

    def test_delete_missing_returns_false(self, store: ChatSessionStore):
        assert store.delete("ghost") is False

    def test_list_ids(self, store: ChatSessionStore):
        s1 = store.create()
        s2 = store.create()
        ids = store.list_ids()
        assert s1.session_id in ids
        assert s2.session_id in ids

    def test_len(self, store: ChatSessionStore):
        assert len(store) == 0
        store.create()
        assert len(store) == 1

    def test_clear(self, store: ChatSessionStore):
        store.create()
        store.create()
        store.clear()
        assert len(store) == 0

    def test_upload_dataset_success(self, store: ChatSessionStore, small_df: pd.DataFrame):
        s = store.create()
        store.upload_dataset(s.session_id, "sales", small_df)
        datasets = store.get_datasets(s.session_id)
        assert "sales" in datasets
        assert len(datasets["sales"]) == 3

    def test_upload_dataset_unknown_session_raises(
        self, store: ChatSessionStore, small_df: pd.DataFrame
    ):
        with pytest.raises(KeyError, match="not found"):
            store.upload_dataset("no-such-session", "df", small_df)

    def test_add_message_and_get_history(self, store: ChatSessionStore):
        s = store.create()
        store.add_message(s.session_id, ChatMessage(role="user", content="hello"))
        store.add_message(s.session_id, ChatMessage(role="assistant", content="hi"))
        history = store.get_history(s.session_id)
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[1].role == "assistant"

    def test_add_message_unknown_session_raises(self, store: ChatSessionStore):
        with pytest.raises(KeyError):
            store.add_message("ghost", ChatMessage(role="user", content="x"))

    def test_get_history_returns_copy(self, store: ChatSessionStore):
        s = store.create()
        h1 = store.get_history(s.session_id)
        h1.append(ChatMessage(role="user", content="injected"))
        h2 = store.get_history(s.session_id)
        assert len(h2) == 0  # original must be unmodified


# ---------------------------------------------------------------------------
# MongoChatSessionStore – same contract, tested with mongomock
# ---------------------------------------------------------------------------


@pytest.fixture()
def mongo_store() -> "MongoChatSessionStore":
    """MongoChatSessionStore backed by an in-memory mongomock client."""
    import mongomock

    return MongoChatSessionStore(_client=mongomock.MongoClient())


class TestMongoChatSessionStore:
    """MongoChatSessionStore behaves identically to ChatSessionStore.

    All tests use mongomock so no real MongoDB instance is required.
    """

    def test_create_generates_uuid(self, mongo_store: MongoChatSessionStore):
        s = mongo_store.create()
        assert len(s.session_id) == 36

    def test_create_with_explicit_id(self, mongo_store: MongoChatSessionStore):
        s = mongo_store.create(session_id="m-sess-1")
        assert s.session_id == "m-sess-1"

    def test_get_existing(self, mongo_store: MongoChatSessionStore):
        s = mongo_store.create()
        fetched = mongo_store.get(s.session_id)
        assert fetched is not None
        assert fetched.session_id == s.session_id

    def test_get_missing_returns_none(self, mongo_store: MongoChatSessionStore):
        assert mongo_store.get("nonexistent") is None

    def test_delete_existing_returns_true(self, mongo_store: MongoChatSessionStore):
        s = mongo_store.create()
        assert mongo_store.delete(s.session_id) is True
        assert mongo_store.get(s.session_id) is None

    def test_delete_missing_returns_false(self, mongo_store: MongoChatSessionStore):
        assert mongo_store.delete("ghost") is False

    def test_list_ids(self, mongo_store: MongoChatSessionStore):
        s1 = mongo_store.create()
        s2 = mongo_store.create()
        ids = mongo_store.list_ids()
        assert s1.session_id in ids
        assert s2.session_id in ids

    def test_len(self, mongo_store: MongoChatSessionStore):
        assert len(mongo_store) == 0
        mongo_store.create()
        assert len(mongo_store) == 1

    def test_clear(self, mongo_store: MongoChatSessionStore):
        mongo_store.create()
        mongo_store.create()
        mongo_store.clear()
        assert len(mongo_store) == 0

    def test_upload_dataset_success(
        self, mongo_store: MongoChatSessionStore, small_df: pd.DataFrame
    ):
        s = mongo_store.create()
        mongo_store.upload_dataset(s.session_id, "sales", small_df)
        datasets = mongo_store.get_datasets(s.session_id)
        assert "sales" in datasets
        assert len(datasets["sales"]) == 3

    def test_upload_dataset_unknown_session_raises(
        self, mongo_store: MongoChatSessionStore, small_df: pd.DataFrame
    ):
        with pytest.raises(KeyError, match="not found"):
            mongo_store.upload_dataset("no-such-session", "df", small_df)

    def test_add_message_and_get_history(self, mongo_store: MongoChatSessionStore):
        s = mongo_store.create()
        mongo_store.add_message(s.session_id, ChatMessage(role="user", content="hello"))
        mongo_store.add_message(s.session_id, ChatMessage(role="assistant", content="hi"))
        history = mongo_store.get_history(s.session_id)
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[1].role == "assistant"

    def test_add_message_unknown_session_raises(self, mongo_store: MongoChatSessionStore):
        with pytest.raises(KeyError):
            mongo_store.add_message("ghost", ChatMessage(role="user", content="x"))

    def test_get_history_key_error_on_missing(self, mongo_store: MongoChatSessionStore):
        with pytest.raises(KeyError):
            mongo_store.get_history("no-session")

    def test_metadata_persisted(self, mongo_store: MongoChatSessionStore):
        s = mongo_store.create(metadata={"user_id": "u42"})
        fetched = mongo_store.get(s.session_id)
        assert fetched.metadata.get("user_id") == "u42"

    def test_multiple_datasets(self, mongo_store: MongoChatSessionStore, small_df: pd.DataFrame):
        s = mongo_store.create()
        mongo_store.upload_dataset(s.session_id, "sales", small_df)
        mongo_store.upload_dataset(s.session_id, "churn", small_df)
        datasets = mongo_store.get_datasets(s.session_id)
        assert "sales" in datasets
        assert "churn" in datasets

    def test_datasets_cleared_on_delete(
        self, mongo_store: MongoChatSessionStore, small_df: pd.DataFrame
    ):
        s = mongo_store.create()
        mongo_store.upload_dataset(s.session_id, "sales", small_df)
        mongo_store.delete(s.session_id)
        # After delete, get should return None and datasets cache must be gone
        assert mongo_store.get(s.session_id) is None

    def test_create_sets_created_at_utc(self, mongo_store: MongoChatSessionStore):
        s = mongo_store.create()
        assert s.created_at.tzinfo is not None

    def test_mongo_store_not_a_langgraph_agent(self, mongo_store: MongoChatSessionStore):
        """MongoChatSessionStore must be a plain Python class."""
        try:
            from ai_data_science_team.templates import BaseAgent

            assert not isinstance(mongo_store, BaseAgent)
        except ImportError:
            pass


class TestIntentRouter:
    """IntentRouter keyword classification."""

    def test_pandas_analyst_turkish(self, router: IntentRouter):
        d = router.route("bu verideki ortalama satış miktarı nedir?")
        assert d.agent_name == "pandas_data_analyst"
        assert d.method == "keyword"

    def test_pandas_analyst_english(self, router: IntentRouter):
        d = router.route("show me the top 5 products by sales")
        assert d.agent_name == "pandas_data_analyst"
        assert d.method == "keyword"

    def test_eda_agent_turkish(self, router: IntentRouter):
        d = router.route("keşifsel veri analizi yap, eksik veri var mı bak")
        assert d.agent_name == "eda_tools_agent"
        assert d.method == "keyword"

    def test_eda_agent_english(self, router: IntentRouter):
        d = router.route("generate an exploratory data analysis profile")
        assert d.agent_name == "eda_tools_agent"

    def test_sql_agent(self, router: IntentRouter):
        d = router.route("run a SQL query to get total revenue by region")
        assert d.agent_name == "sql_data_analyst"

    def test_data_cleaning_agent_turkish(self, router: IntentRouter):
        d = router.route("veriyi temizle, eksik değerleri doldur")
        assert d.agent_name == "data_cleaning_agent"

    def test_anomaly_detection_agent_turkish(self, router: IntentRouter):
        d = router.route("anomali tespiti yap, aykırı değerleri bul")
        assert d.agent_name == "anomaly_detection_agent"

    def test_anomaly_detection_agent_english(self, router: IntentRouter):
        d = router.route("detect anomalies in this dataset")
        assert d.agent_name == "anomaly_detection_agent"

    def test_document_parser_url(self, router: IntentRouter):
        d = router.route("bu url'den veri çek: https://example.com/data")
        assert d.agent_name == "document_parser_agent"

    def test_api_connector(self, router: IntentRouter):
        d = router.route("call this REST API endpoint and get the data")
        assert d.agent_name == "api_connector_agent"

    def test_no_hit_returns_default(self, router: IntentRouter):
        d = router.route("benim adım ne")  # not data-related
        assert d.agent_name == _DEFAULT_AGENT
        assert d.method == "default"

    def test_confidence_is_normalised(self, router: IntentRouter):
        d = router.route("explore the missing data and run eda analysis profil")
        assert 0.0 <= d.confidence <= 1.0

    def test_router_decision_fields(self, router: IntentRouter):
        d = router.route("anomaly detect")
        assert isinstance(d, RouterDecision)
        assert isinstance(d.raw_scores, dict)
        assert isinstance(d.confidence, float)
        assert d.method in ("keyword", "llm", "default")


class TestIntentMap:
    """INTENT_MAP structure checks."""

    def test_required_agents_present(self):
        required = {
            "pandas_data_analyst",
            "eda_tools_agent",
            "sql_data_analyst",
            "data_cleaning_agent",
            "anomaly_detection_agent",
            "document_parser_agent",
            "api_connector_agent",
            "model_serving_agent",
        }
        assert required.issubset(set(INTENT_MAP.keys()))

    def test_all_agents_have_keywords(self):
        for agent, keywords in INTENT_MAP.items():
            assert len(keywords) >= 3, f"{agent} has too few keywords"


class TestExtractResponse:
    """_extract_response() module-level helper."""

    def _make_mock_agent(self, response_dict: Dict[str, Any]):
        """Create a minimal mock that looks like a BaseAgent post-invoke."""
        mock = MagicMock()
        mock.response = response_dict
        return mock

    def test_extracts_text_from_ai_message(self):
        agent = self._make_mock_agent({"messages": [AIMessage(content="Here is your analysis.")]})
        text, art_type, art_data = _extract_response(agent)
        assert "analysis" in text
        assert art_type is None

    def test_extracts_table_artifact_from_data_wrangled(self, small_df: pd.DataFrame):
        agent = self._make_mock_agent(
            {
                "messages": [AIMessage(content="Done.")],
                "data_wrangled": small_df.to_dict(),
            }
        )
        text, art_type, art_data = _extract_response(agent)
        assert art_type == "table"
        assert "records" in art_data
        assert "columns" in art_data
        assert len(art_data["records"]) == 3

    def test_extracts_chart_artifact_from_plotly_graph(self):
        mock_chart = {"data": [{"type": "bar", "x": [1, 2], "y": [3, 4]}], "layout": {}}
        agent = self._make_mock_agent(
            {
                "messages": [AIMessage(content="Chart ready.")],
                "plotly_graph": mock_chart,
            }
        )
        text, art_type, art_data = _extract_response(agent)
        assert art_type == "chart"
        assert art_data == mock_chart

    def test_empty_response_returns_fallback_text(self):
        agent = self._make_mock_agent({})
        text, art_type, art_data = _extract_response(agent)
        assert isinstance(text, str)
        assert art_type is None


# ---------------------------------------------------------------------------
# ═══════════════════════════════════════════════════════════════
# TG2 — Integration tests (real gpt-4o-mini)
# ═══════════════════════════════════════════════════════════════
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def llm():
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=OPENAI_API_KEY)


@pytest.fixture(scope="module")
def workspace(llm) -> ChatWorkspace:
    return ChatWorkspace(model=llm, agent_kwargs={"max_retries": 1})


@pytest.fixture(scope="module")
def sales_df() -> pd.DataFrame:
    import pathlib

    data_path = pathlib.Path(__file__).parent.parent / "data" / "bike_sales_data.csv"
    if data_path.exists():
        return pd.read_csv(data_path)
    return pd.DataFrame(
        {"product": ["Bike A", "Bike B"], "sales": [100, 200], "category": ["MTB", "Road"]}
    )


@pytest.mark.integration
@skip_no_key
class TestChatWorkspaceIntegration:
    """Integration tests — real LLM, data analysis tasks."""

    def test_create_session_and_upload(self, workspace: ChatWorkspace, sales_df: pd.DataFrame):
        sid = workspace.create_session(metadata={"test": "tg2"})
        workspace.upload_dataset(sid, "sales", sales_df)
        session = workspace.get_session(sid)
        assert "sales" in session.datasets
        assert len(session.datasets["sales"]) > 0

    def test_chat_returns_valid_response(self, workspace: ChatWorkspace, sales_df: pd.DataFrame):
        sid = workspace.create_session()
        workspace.upload_dataset(sid, "sales", sales_df)
        resp = workspace.chat(sid, "how many rows does this dataset have?")
        assert isinstance(resp, ChatResponse)
        assert isinstance(resp.text, str) and len(resp.text) > 0
        assert resp.session_id == sid
        assert resp.duration_ms > 0

    def test_chat_routing_decision_is_populated(
        self, workspace: ChatWorkspace, sales_df: pd.DataFrame
    ):
        sid = workspace.create_session()
        workspace.upload_dataset(sid, "sales", sales_df)
        resp = workspace.chat(sid, "show me a statistical summary of this data")
        assert resp.routing is not None
        assert resp.routing.agent_name in (
            "pandas_data_analyst",
            "eda_tools_agent",
            "data_cleaning_agent",
        )

    def test_history_populated_after_chat(self, workspace: ChatWorkspace, sales_df: pd.DataFrame):
        sid = workspace.create_session()
        workspace.upload_dataset(sid, "sales", sales_df)
        workspace.chat(sid, "what is this data about?")
        history = workspace.get_history(sid)
        # At minimum: 1 user + 1 assistant message
        assert len(history) >= 2
        roles = [m.role for m in history]
        assert "user" in roles
        assert "assistant" in roles


# ---------------------------------------------------------------------------
# ═══════════════════════════════════════════════════════════════
# TG3 — E2E sanity tests
# ═══════════════════════════════════════════════════════════════
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestM21E2E:
    """E2E sanity: import check, architecture constraint, pipeline smoke."""

    def test_all_m21_symbols_importable(self):
        """All public M21 symbols should be importable from multiagents."""
        from ai_data_science_team.multiagents import (
            INTENT_MAP,
            ChatWorkspace,
            IntentRouter,
            MongoChatSessionStore,
        )

        assert ChatWorkspace is not None
        assert IntentRouter is not None
        assert isinstance(INTENT_MAP, dict)
        assert MongoChatSessionStore is not None

    def test_chat_workspace_is_not_a_langgraph_agent(self):
        """ChatWorkspace must be a plain Python class — not a BaseAgent subclass.

        Adding another LangGraph layer for routing would be unnecessary
        complexity (Anthropic best-practices: prefer simple routing workflows
        over nested agent architectures).
        """
        try:
            from ai_data_science_team.templates import BaseAgent

            assert not issubclass(ChatWorkspace, BaseAgent), (
                "ChatWorkspace must NOT extend BaseAgent — it is a plain Python orchestrator class."
            )
        except ImportError:
            pass  # BaseAgent unavailable in stripped env — skip check

    def test_chat_workspace_is_plain_class(self):
        from ai_data_science_team.multiagents import ChatWorkspace

        # Should be directly instantiable without a compiled graph
        mock_llm = MagicMock()
        ws = ChatWorkspace(model=mock_llm)
        assert isinstance(ws, ChatWorkspace)
        assert hasattr(ws, "create_session")
        assert hasattr(ws, "upload_dataset")
        assert hasattr(ws, "chat")
        assert hasattr(ws, "get_history")
        assert hasattr(ws, "delete_session")

    def test_session_lifecycle_without_llm(self, small_df: pd.DataFrame):
        """Full session lifecycle: create → upload → message → delete."""
        mock_llm = MagicMock()
        ws = ChatWorkspace(model=mock_llm)

        # Create
        sid = ws.create_session(metadata={"user": "test"})
        assert sid in ws.list_sessions()

        # Upload
        ws.upload_dataset(sid, "data", small_df)
        session = ws.get_session(sid)
        assert "data" in session.datasets

        # History starts empty
        assert ws.get_history(sid) == []

        # Delete
        assert ws.delete_session(sid) is True
        assert sid not in ws.list_sessions()
        assert ws.delete_session(sid) is False  # second delete returns False
