"""TG1 / TG2 / TG3 — Tests for M25 API Connector, Document Parser & Model Serving Agents.

Test Groups
-----------
TG1 (unit tests, no LLM required):
    * APIConnectorAgent tools via .func()    — call_api, parse_response, get_api_params  (6 tests)
    * DocumentParserAgent tools via .func()  — parse_document, extract_tables, params    (6 tests)
    * ModelServingAgent tools via .func()    — load_model, run_inference, params          (6 tests)

TG2 (integration tests, real gpt-4o-mini):
    * APIConnectorAgent.invoke_agent()       — 4 tests
    * DocumentParserAgent.invoke_agent()     — 4 tests
    * ModelServingAgent.invoke_agent()       — 4 tests

TG3 (e2e tests, no LLM):
    * Import check from agents.__init__       (1 test)
    * Factory functions importable            (1 test)
    * Full parse → serve pipeline             (1 test)

Run all:
    pytest tests/test_m25_agents.py -v

Skip LLM tests:
    pytest tests/test_m25_agents.py -v -m "not integration and not e2e"

Run only integration:
    pytest tests/test_m25_agents.py -v -m integration
"""
from __future__ import annotations

import json
import os
import pickle
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Markers / skip helpers
# ---------------------------------------------------------------------------
pytestmark = pytest.mark.m25

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
skip_no_key = pytest.mark.skipif(
    not OPENAI_API_KEY,
    reason="OPENAI_API_KEY is not set — skipping LLM-dependent test",
)

langchain_openai = pytest.importorskip(
    "langchain_openai",
    reason="langchain_openai is not installed — skipping M25 tests",
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = _REPO_ROOT / "data"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def bike_df() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "bike_sales_data.csv")


@pytest.fixture(scope="session")
def churn_df() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "churn_data.csv")


@pytest.fixture(scope="session")
def html_content() -> str:
    return """
    <html>
    <head><title>Test Document</title></head>
    <body>
        <h1>Sales Report</h1>
        <p>This is a test document with tabular data.</p>
        <table>
            <tr><th>Product</th><th>Sales</th><th>Region</th></tr>
            <tr><td>Bike A</td><td>150</td><td>North</td></tr>
            <tr><td>Bike B</td><td>230</td><td>South</td></tr>
            <tr><td>Bike C</td><td>190</td><td>East</td></tr>
        </table>
        <p>Total sales have increased 15% year-over-year.</p>
    </body>
    </html>
    """


@pytest.fixture(scope="session")
def classification_model_path(churn_df: pd.DataFrame) -> str:
    """Trains a simple RF classifier on churn data and saves it to a temp pkl file."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import LabelEncoder

    df = churn_df.copy()
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce").fillna(0)
    features = ["tenure", "MonthlyCharges", "TotalCharges"]
    X = df[features].astype(float)
    y = LabelEncoder().fit_transform(df["Churn"].fillna("No"))

    clf = RandomForestClassifier(n_estimators=10, random_state=42)
    clf.fit(X, y)

    tmp = tempfile.NamedTemporaryFile(suffix=".pkl", delete=False)
    with open(tmp.name, "wb") as fh:
        pickle.dump(clf, fh)

    yield tmp.name

    # Cleanup
    try:
        os.unlink(tmp.name)
    except Exception:
        pass


@pytest.fixture(scope="session")
def llm():
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model="gpt-4o-mini", temperature=0)


# ---------------------------------------------------------------------------
# Local mock HTTP server (no internet required — fast integration tests)
# ---------------------------------------------------------------------------
_MOCK_POST = {"id": 1, "title": "Test Post", "body": "Hello world", "userId": 1}
_MOCK_POSTS = [{"id": i, "title": f"Post {i}", "userId": 1} for i in range(1, 101)]  # 100 items
_MOCK_USERS = [{"id": i, "name": f"User {i}", "email": f"user{i}@example.com"} for i in range(1, 11)]
_MOCK_TODO = {"id": 1, "title": "Test todo", "completed": False, "userId": 1}


class _MockRequestHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler serving pre-defined JSON fixtures."""

    def log_message(self, fmt, *args):  # silence request logs during tests
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")
        if path == "/posts/1":
            self._send_json(_MOCK_POST)
        elif path == "/posts":
            self._send_json(_MOCK_POSTS)
        elif path == "/users":
            self._send_json(_MOCK_USERS)
        elif path == "/todos/1":
            self._send_json(_MOCK_TODO)
        else:
            self._send_json({"error": "not found"}, 404)


@pytest.fixture(scope="session")
def local_api_server():
    """Starts a local HTTP server in a daemon thread. Returns base URL."""
    server = HTTPServer(("127.0.0.1", 0), _MockRequestHandler)  # port=0 → OS picks free port
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()

# ===========================================================================
# TG1 — Unit tests (no LLM, tool .func() calls)
# ===========================================================================


class TestAPIConnectorToolUnit:
    """TG1: Direct tool function tests for APIConnectorAgent (no LLM)."""

    def test_call_api_public_json(self):
        """call_api fetches a real public JSON endpoint."""
        from ai_data_science_team.agents.api_connector_agent import call_api

        content, artifact = call_api.func(
            url="https://jsonplaceholder.typicode.com/todos/1",
            method="GET",
            auth_scheme="none",
            auth_credentials={},
            headers={},
            params={},
            body={},
            response_format="json",
            timeout=15,
        )
        assert artifact.get("status_code") == 200
        assert artifact.get("ok") is True
        assert isinstance(artifact.get("response_body"), dict)

    def test_call_api_invalid_url_returns_error(self):
        """call_api on an unreachable host returns an error artifact gracefully."""
        from ai_data_science_team.agents.api_connector_agent import call_api

        content, artifact = call_api.func(
            url="http://this-host-does-not-exist-xyz.invalid/path",
            method="GET",
            auth_scheme="none",
            auth_credentials={},
            headers={},
            params={},
            body={},
            response_format="json",
            timeout=5,
        )
        assert "error" in artifact or artifact.get("ok") is False

    def test_parse_response_extracts_fields(self):
        """parse_response correctly extracts dot-notation fields from a nested dict."""
        from ai_data_science_team.agents.api_connector_agent import parse_response

        api_results = {
            "status_code": 200,
            "ok": True,
            "response_body": {"data": {"user": {"name": "Alice", "age": 30}}, "total": 1},
        }
        content, artifact = parse_response.func(
            url="https://example.com",
            response_format="json",
            extract_fields=["data.user.name", "data.user.age", "total"],
            api_results=api_results,
        )
        assert artifact["extracted_fields"]["data.user.name"] == "Alice"
        assert artifact["extracted_fields"]["data.user.age"] == 30
        assert artifact["extracted_fields"]["total"] == 1

    def test_parse_response_counts_records(self):
        """parse_response detects record count from a list-body response."""
        from ai_data_science_team.agents.api_connector_agent import parse_response

        api_results = {
            "status_code": 200,
            "ok": True,
            "response_body": [{"id": i} for i in range(25)],
        }
        _, artifact = parse_response.func(
            url="https://example.com",
            response_format="json",
            extract_fields=[],
            api_results=api_results,
        )
        assert artifact["record_count"] == 25

    def test_parse_response_empty_results(self):
        """parse_response returns error gracefully when api_results is empty."""
        from ai_data_science_team.agents.api_connector_agent import parse_response

        content, artifact = parse_response.func(
            url="https://example.com",
            response_format="json",
            extract_fields=[],
            api_results={},
        )
        assert "No API results" in content

    def test_get_api_params_summary(self):
        """get_api_params returns a string containing key config values."""
        from ai_data_science_team.agents.api_connector_agent import get_api_params

        result = get_api_params.func(
            url="https://api.example.com",
            http_method="POST",
            auth_scheme="bearer",
            response_format="json",
            timeout=30,
        )
        assert "https://api.example.com" in result
        assert "POST" in result
        assert "bearer" in result


class TestDocumentParserToolUnit:
    """TG1: Direct tool function tests for DocumentParserAgent (no LLM)."""

    def test_parse_html_text(self, html_content):
        """parse_document extracts clean text from an HTML string."""
        from ai_data_science_team.agents.document_parser_agent import parse_document

        content, artifact = parse_document.func(
            document_source=html_content,
            document_type="html",
            extraction_mode="text",
            max_pages=0,
        )
        assert artifact.get("document_type") == "html"
        assert "Sales Report" in artifact.get("text", "")
        assert artifact.get("word_count", 0) > 0

    def test_parse_html_tables(self, html_content):
        """parse_document extracts tables from HTML in 'tables' mode."""
        from ai_data_science_team.agents.document_parser_agent import parse_document

        _, artifact = parse_document.func(
            document_source=html_content,
            document_type="html",
            extraction_mode="tables",
            max_pages=0,
        )
        assert artifact.get("n_tables", 0) >= 1

    def test_parse_txt_raw_string(self):
        """parse_document handles plain text content passed as a raw string."""
        from ai_data_science_team.agents.document_parser_agent import parse_document

        raw = "Hello world. This is a test document.\nLine two."
        _, artifact = parse_document.func(
            document_source=raw,
            document_type="txt",
            extraction_mode="text",
            max_pages=0,
        )
        assert "Hello world" in artifact.get("text", "")
        assert artifact.get("word_count", 0) >= 5

    def test_extract_tables_from_html_parse(self, html_content):
        """extract_tables converts raw HTML table rows into structured records."""
        from ai_data_science_team.agents.document_parser_agent import (
            extract_tables,
            parse_document,
        )

        _, parse_artifact = parse_document.func(
            document_source=html_content,
            document_type="html",
            extraction_mode="tables",
            max_pages=0,
        )
        _, tbl_artifact = extract_tables.func(
            document_source="<html>",
            document_type="html",
            parse_results=parse_artifact,
        )
        assert tbl_artifact.get("table_count", 0) >= 1

    def test_extract_tables_empty_parse_results(self):
        """extract_tables returns gracefully when no parse_results present."""
        from ai_data_science_team.agents.document_parser_agent import extract_tables

        content, artifact = extract_tables.func(
            document_source="",
            document_type="html",
            parse_results={},
        )
        assert "No parse_results" in content

    def test_get_parser_params_summary(self):
        """get_parser_params returns a config summary string."""
        from ai_data_science_team.agents.document_parser_agent import get_parser_params

        result = get_parser_params.func(
            document_type="pdf",
            extraction_mode="full",
            max_pages=5,
        )
        assert "pdf" in result
        assert "full" in result
        assert "max_pages=5" in result


class TestModelServingToolUnit:
    """TG1: Direct tool function tests for ModelServingAgent (no LLM)."""

    def test_load_model_local_pkl(self, classification_model_path):
        """load_model loads a local pickle file and returns metadata."""
        from ai_data_science_team.agents.g3_model_serving_agent import load_model

        content, artifact = load_model.func(
            model_uri=classification_model_path,
            task_type="classification",
        )
        assert artifact.get("loaded") is True
        assert "RandomForest" in artifact.get("model_type", "")
        assert artifact.get("task_type") == "classification"

    def test_load_model_missing_file(self):
        """load_model returns an error artifact for a non-existent file path."""
        from ai_data_science_team.agents.g3_model_serving_agent import load_model

        content, artifact = load_model.func(
            model_uri="/tmp/no_such_model_xyz.pkl",
            task_type="auto",
        )
        assert "error" in artifact

    def test_load_model_empty_uri(self):
        """load_model returns error when model_uri is empty."""
        from ai_data_science_team.agents.g3_model_serving_agent import load_model

        content, artifact = load_model.func(
            model_uri="",
            task_type="auto",
        )
        assert "error" in artifact

    def test_run_inference_after_load(self, classification_model_path, churn_df):
        """run_inference produces predictions after loading the model."""
        from ai_data_science_team.agents.g3_model_serving_agent import (
            load_model,
            run_inference,
        )

        load_model.func(model_uri=classification_model_path, task_type="classification")

        df = churn_df.copy()
        df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce").fillna(0)
        features = ["tenure", "MonthlyCharges", "TotalCharges"]
        X = df[features].astype(float).head(20)

        _, artifact = run_inference.func(
            model_uri=classification_model_path,
            input_data_raw=X.to_dict(),
            task_type="classification",
            serving_results={},
        )
        assert artifact.get("n_samples") == 20
        assert len(artifact.get("predictions", [])) == 20
        assert artifact.get("probabilities") is not None

    def test_run_inference_empty_input(self, classification_model_path):
        """run_inference returns error gracefully on empty input."""
        from ai_data_science_team.agents.g3_model_serving_agent import run_inference

        content, artifact = run_inference.func(
            model_uri=classification_model_path,
            input_data_raw={},
            task_type="classification",
            serving_results={},
        )
        assert "error" in artifact or "empty" in content.lower()

    def test_get_serving_params_summary(self, classification_model_path):
        """get_serving_params returns a config summary string."""
        from ai_data_science_team.agents.g3_model_serving_agent import get_serving_params

        result = get_serving_params.func(
            model_uri=classification_model_path,
            task_type="classification",
        )
        assert "classification" in result

    def test_health_check_ready_after_load(self, classification_model_path):
        """health_check reports READY after the model has been loaded into the registry."""
        from ai_data_science_team.agents.g3_model_serving_agent import (
            health_check,
            load_model,
        )

        # Ensure model is in the registry
        load_model.func(model_uri=classification_model_path, task_type="classification")

        content, artifact = health_check.func(
            model_uri=classification_model_path,
            task_type="classification",
            serving_results={},
        )
        assert artifact.get("model_in_registry") is True
        assert artifact.get("has_predict") is True
        assert artifact.get("smoke_test_passed") is True
        assert artifact.get("ready") is True
        assert "READY" in content

    def test_health_check_fails_unloaded_model(self):
        """health_check reports FAILED when model was never loaded into registry."""
        from ai_data_science_team.agents.g3_model_serving_agent import health_check

        content, artifact = health_check.func(
            model_uri="/tmp/never_loaded_model.pkl",
            task_type="classification",
            serving_results={},
        )
        assert artifact.get("model_in_registry") is False
        assert artifact.get("ready") is False
        assert "FAILED" in content


# ===========================================================================
# TG2 — Integration tests (real LLM)
# ===========================================================================


class TestAPIConnectorIntegration:
    """TG2: APIConnectorAgent end-to-end with real LLM (local mock server)."""

    @pytest.mark.integration
    @skip_no_key
    def test_get_public_json_api(self, llm, local_api_server):
        """Agent calls a local mock JSON API and returns structured results."""
        from ai_data_science_team.agents.api_connector_agent import APIConnectorAgent

        agent = APIConnectorAgent(
            model=llm,
            url=f"{local_api_server}/posts/1",
            http_method="GET",
            response_format="json",
        )
        agent.invoke_agent()
        assert agent.get_status_code() == 200
        assert agent.is_ok() is True
        assert isinstance(agent.get_response_body(), dict)

    @pytest.mark.integration
    @skip_no_key
    def test_get_json_list_and_count(self, llm, local_api_server):
        """Agent fetches a list endpoint and reports record count."""
        from ai_data_science_team.agents.api_connector_agent import APIConnectorAgent

        agent = APIConnectorAgent(
            model=llm,
            url=f"{local_api_server}/posts",
            http_method="GET",
            response_format="json",
        )
        agent.invoke_agent()
        assert agent.get_status_code() == 200
        rc = agent.get_record_count()
        assert rc is not None and rc > 0

    @pytest.mark.integration
    @skip_no_key
    def test_response_as_dataframe(self, llm, local_api_server):
        """Agent converts list response to a DataFrame."""
        from ai_data_science_team.agents.api_connector_agent import APIConnectorAgent

        agent = APIConnectorAgent(
            model=llm,
            url=f"{local_api_server}/users",
            response_format="json",
        )
        agent.invoke_agent()
        df = agent.get_response_as_dataframe()
        assert df is not None
        assert len(df) > 0

    @pytest.mark.integration
    @skip_no_key
    def test_ai_message_not_empty(self, llm, local_api_server):
        """Agent produces a non-empty AI summary message."""
        from ai_data_science_team.agents.api_connector_agent import APIConnectorAgent

        agent = APIConnectorAgent(
            model=llm,
            url=f"{local_api_server}/todos/1",
        )
        agent.invoke_agent()
        msg = agent.get_ai_message()
        assert msg and len(msg) > 0


class TestDocumentParserIntegration:
    """TG2: DocumentParserAgent end-to-end with real LLM."""

    @pytest.mark.integration
    @skip_no_key
    def test_parse_html_text_mode(self, llm, html_content):
        """Agent extracts text from an HTML document."""
        from ai_data_science_team.agents.document_parser_agent import (
            DocumentParserAgent,
        )

        agent = DocumentParserAgent(
            model=llm,
            document_type="html",
            extraction_mode="text",
        )
        agent.invoke_agent(document_source=html_content)
        assert agent.get_text() is not None
        assert agent.get_word_count() > 0

    @pytest.mark.integration
    @skip_no_key
    def test_parse_html_tables_mode(self, llm, html_content):
        """Agent extracts tables from HTML in tables mode."""
        from ai_data_science_team.agents.document_parser_agent import (
            DocumentParserAgent,
        )

        agent = DocumentParserAgent(
            model=llm,
            document_type="html",
            extraction_mode="tables",
        )
        agent.invoke_agent(document_source=html_content)
        assert agent.get_n_tables() is not None

    @pytest.mark.integration
    @skip_no_key
    def test_parse_raw_text(self, llm):
        """Agent parses a plain text document."""
        from ai_data_science_team.agents.document_parser_agent import (
            DocumentParserAgent,
        )

        raw = "Machine learning model performance report.\nAccuracy: 92%.\nF1: 0.91."
        agent = DocumentParserAgent(model=llm, document_type="txt")
        agent.invoke_agent(document_source=raw)
        assert agent.get_text() is not None
        assert "Machine learning" in agent.get_text()

    @pytest.mark.integration
    @skip_no_key
    def test_ai_message_not_empty(self, llm, html_content):
        """Agent returns a non-empty AI summary message."""
        from ai_data_science_team.agents.document_parser_agent import (
            DocumentParserAgent,
        )

        agent = DocumentParserAgent(model=llm, document_type="html")
        agent.invoke_agent(document_source=html_content)
        msg = agent.get_ai_message()
        assert msg and len(msg) > 0


class TestModelServingIntegration:
    """TG2: ModelServingAgent end-to-end with real LLM."""

    @pytest.mark.integration
    @skip_no_key
    def test_load_and_infer_classification(self, llm, classification_model_path, churn_df):
        """Agent loads a local pkl classifier and runs inference."""
        from ai_data_science_team.agents.g3_model_serving_agent import ModelServingAgent

        df = churn_df.copy()
        df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce").fillna(0)
        X = df[["tenure", "MonthlyCharges", "TotalCharges"]].astype(float).head(10)

        agent = ModelServingAgent(
            model=llm,
            model_uri=classification_model_path,
            task_type="classification",
        )
        agent.invoke_agent(input_data=X)
        preds = agent.get_predictions()
        assert preds is not None
        assert len(preds) == 10

    @pytest.mark.integration
    @skip_no_key
    def test_predictions_as_dataframe(self, llm, classification_model_path, churn_df):
        """Agent returns predictions as a structured DataFrame."""
        from ai_data_science_team.agents.g3_model_serving_agent import ModelServingAgent

        df = churn_df.copy()
        df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce").fillna(0)
        X = df[["tenure", "MonthlyCharges", "TotalCharges"]].astype(float).head(15)

        agent = ModelServingAgent(
            model=llm,
            model_uri=classification_model_path,
            task_type="classification",
        )
        agent.invoke_agent(input_data=X)
        df_out = agent.get_predictions_as_dataframe()
        assert df_out is not None
        assert "prediction" in df_out.columns
        assert len(df_out) == 15

    @pytest.mark.integration
    @skip_no_key
    def test_pred_distribution(self, llm, classification_model_path, churn_df):
        """Agent returns prediction distribution for a classifier."""
        from ai_data_science_team.agents.g3_model_serving_agent import ModelServingAgent

        df = churn_df.copy()
        df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce").fillna(0)
        X = df[["tenure", "MonthlyCharges", "TotalCharges"]].astype(float).head(50)

        agent = ModelServingAgent(
            model=llm,
            model_uri=classification_model_path,
            task_type="classification",
        )
        agent.invoke_agent(input_data=X)
        dist = agent.get_pred_distribution()
        assert dist is not None
        assert sum(dist.values()) == 50

    @pytest.mark.integration
    @skip_no_key
    def test_ai_message_not_empty(self, llm, classification_model_path, churn_df):
        """Agent returns a non-empty AI summary message."""
        from ai_data_science_team.agents.g3_model_serving_agent import ModelServingAgent

        df = churn_df.copy()
        df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce").fillna(0)
        X = df[["tenure", "MonthlyCharges", "TotalCharges"]].astype(float).head(5)

        agent = ModelServingAgent(
            model=llm,
            model_uri=classification_model_path,
        )
        agent.invoke_agent(input_data=X)
        msg = agent.get_ai_message()
        assert msg and len(msg) > 0


# ===========================================================================
# TG3 — E2E tests (no LLM)
# ===========================================================================


class TestM25E2E:
    """TG3: end-to-end / integration tests that do NOT require an LLM."""

    def test_import_from_agents_init(self):
        """All 3 M25 agent classes and factories are importable from agents.__init__."""
        from ai_data_science_team.agents import (
            APIConnectorAgent,
            DocumentParserAgent,
            ModelServingAgent,
            make_api_connector_agent,
            make_document_parser_agent,
            make_model_serving_agent,
        )

        assert callable(make_api_connector_agent)
        assert callable(make_document_parser_agent)
        assert callable(make_model_serving_agent)

        from ai_data_science_team.templates import BaseAgent

        assert issubclass(APIConnectorAgent, BaseAgent), "APIConnectorAgent must extend BaseAgent"
        assert issubclass(DocumentParserAgent, BaseAgent), "DocumentParserAgent must extend BaseAgent"
        assert issubclass(ModelServingAgent, BaseAgent), "ModelServingAgent must extend BaseAgent"

    def test_tool_modules_importable(self):
        """All tool lists from the 3 M25 agent modules are importable."""
        from ai_data_science_team.agents.api_connector_agent import API_TOOLS
        from ai_data_science_team.agents.document_parser_agent import PARSER_TOOLS
        from ai_data_science_team.agents.g3_model_serving_agent import SERVING_TOOLS

        assert len(API_TOOLS) >= 3
        assert len(PARSER_TOOLS) >= 3
        assert len(SERVING_TOOLS) >= 4   # load_model, run_inference, health_check, get_serving_params

    def test_parse_then_serve_pipeline(self, html_content, classification_model_path, churn_df):
        """Tool-level pipeline: parse HTML doc → save text → load model → run inference."""
        from ai_data_science_team.agents.document_parser_agent import parse_document
        from ai_data_science_team.agents.g3_model_serving_agent import (
            load_model,
            run_inference,
        )

        # Step 1: parse HTML document
        _, parse_artifact = parse_document.func(
            document_source=html_content,
            document_type="html",
            extraction_mode="full",
            max_pages=0,
        )
        assert parse_artifact.get("word_count", 0) > 0

        # Step 2: load model
        _, load_artifact = load_model.func(
            model_uri=classification_model_path,
            task_type="classification",
        )
        assert load_artifact.get("loaded") is True

        # Step 3: run inference
        df = churn_df.copy()
        df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce").fillna(0)
        X = df[["tenure", "MonthlyCharges", "TotalCharges"]].astype(float).head(5)
        _, infer_artifact = run_inference.func(
            model_uri=classification_model_path,
            input_data_raw=X.to_dict(),
            task_type="classification",
            serving_results=load_artifact,
        )
        assert infer_artifact.get("n_samples") == 5
        assert len(infer_artifact.get("predictions", [])) == 5
