"""TG1 / TG2 / TG3 — Tests for M23 Anomaly Detection & Model Explainability Agents.

Test Groups
-----------
TG1 (unit tests, no LLM required):
    * Tool functions directly via .func() — AnomalyDetection tools (5 tests)
    * Tool functions directly — ModelExplainability tools (5 tests)

TG2 (integration tests, real gpt-4o-mini):
    * AnomalyDetectionAgent.invoke_agent() end-to-end (4 tests)
    * ModelExplainabilityAgent.invoke_agent() end-to-end (4 tests)

TG3 (e2e tests, real gpt-4o-mini):
    * Import check from agents.__init__ (1 test, no LLM)
    * Full anomaly → explainability pipeline  (2 tests)

Run all:
    pytest tests/test_m23_agents.py -v

Skip LLM tests:
    pytest tests/test_m23_agents.py -v -m "not integration and not e2e"

Run only integration:
    pytest tests/test_m23_agents.py -v -m integration
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Shared skip / marker helpers
# ---------------------------------------------------------------------------
pytestmark = pytest.mark.m23

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
skip_no_key = pytest.mark.skipif(
    not OPENAI_API_KEY,
    reason="OPENAI_API_KEY is not set — skipping LLM-dependent test",
)

langchain_openai = pytest.importorskip(
    "langchain_openai",
    reason="langchain_openai is not installed — skipping M23 tests",
)

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = _REPO_ROOT / "data"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def bike_df() -> pd.DataFrame:
    """Load the bike sales dataset."""
    df = pd.read_csv(DATA_DIR / "bike_sales_data.csv")
    return df


@pytest.fixture(scope="session")
def churn_df() -> pd.DataFrame:
    """Load the churn dataset (raw)."""
    df = pd.read_csv(DATA_DIR / "churn_data.csv")
    return df


@pytest.fixture(scope="session")
def churn_numeric_df(churn_df: pd.DataFrame) -> pd.DataFrame:
    """Numeric-only feature columns from churn data (no target, no ID)."""
    df = churn_df.copy()
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")
    cols = ["tenure", "MonthlyCharges", "TotalCharges"]
    return df[cols].fillna(0).astype(float)


@pytest.fixture(scope="session")
def churn_model_data(churn_df: pd.DataFrame) -> Dict[str, Any]:
    """Train a RandomForestClassifier on churn data.  Returns dict with model + splits."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split

    df = churn_df.copy()
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")
    df = df.fillna(0)

    feature_cols = ["tenure", "MonthlyCharges", "TotalCharges"]
    df = df[feature_cols + ["Churn"]].copy()
    df["Churn"] = (df["Churn"].astype(str).str.lower().isin(["yes", "1", "true"])).astype(int)

    X = df[feature_cols].astype(float)
    y = df["Churn"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    clf = RandomForestClassifier(n_estimators=20, random_state=42, max_depth=5)
    clf.fit(X_train, y_train)

    return {
        "model": clf,
        "X_train": X_train,
        "X_test": X_test,
        "y_train": y_train,
        "y_test": y_test,
        "feature_names": feature_cols,
    }


@pytest.fixture(scope="session")
def llm():
    """Real gpt-4o-mini LLM.  Skips if OPENAI_API_KEY is not set."""
    if not OPENAI_API_KEY:
        pytest.skip("OPENAI_API_KEY is not set")
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model="gpt-4o-mini", temperature=0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _invoke_safe(agent, **kwargs):
    """Invoke agent, skipping if OpenAI quota is exhausted."""
    try:
        agent.invoke_agent(**kwargs)
    except Exception as exc:
        err = str(exc)
        if any(x in err for x in ("insufficient_quota", "RateLimitError", "rate_limit")):
            pytest.skip("OpenAI quota exhausted")
        raise


# ===========================================================================
# TG1 — Unit tests (no LLM needed, call tool .func() directly)
# ===========================================================================


class TestAnomalyDetectionToolUnit:
    """Call anomaly detection tool functions directly (no LLM)."""

    def test_detect_anomalies_isolation_forest(self, churn_numeric_df):
        """IsolationForest returns correct artifact structure."""
        from ai_data_science_team.agents.anomaly_detection_agent import detect_anomalies

        content, artifact = detect_anomalies.func(
            data_raw=churn_numeric_df.to_dict(),
            method="IsolationForest",
            contamination=0.05,
        )

        assert isinstance(content, str)
        assert "anomaly" in content.lower()
        assert "method" in artifact
        assert artifact["method"] == "IsolationForest"
        assert "n_anomalies" in artifact
        assert "anomaly_rate" in artifact
        assert "anomaly_indices" in artifact
        assert isinstance(artifact["anomaly_indices"], list)
        assert artifact["n_anomalies"] > 0
        assert 0.0 <= artifact["anomaly_rate"] <= 1.0

    def test_detect_anomalies_lof(self, churn_numeric_df):
        """LOF returns anomaly indices and scores."""
        from ai_data_science_team.agents.anomaly_detection_agent import detect_anomalies

        content, artifact = detect_anomalies.func(
            data_raw=churn_numeric_df.to_dict(),
            method="LOF",
            contamination=0.05,
        )

        assert artifact["method"] == "LOF"
        assert len(artifact["anomaly_indices"]) == artifact["n_anomalies"]
        assert len(artifact["anomaly_scores"]) == artifact["total_samples"]

    def test_detect_anomalies_autoensemble(self, churn_numeric_df):
        """AutoEnsemble (majority vote) runs without error."""
        from ai_data_science_team.agents.anomaly_detection_agent import detect_anomalies

        content, artifact = detect_anomalies.func(
            data_raw=churn_numeric_df.to_dict(),
            method="AutoEnsemble",
            contamination=0.05,
        )

        assert artifact["method"] == "AutoEnsemble"
        assert artifact["total_samples"] == len(churn_numeric_df)
        assert 0 <= artifact["n_anomalies"] <= artifact["total_samples"]

    def test_detect_anomalies_bike_numeric_cols(self, bike_df):
        """Works on bike sales data (numeric columns only)."""
        from ai_data_science_team.agents.anomaly_detection_agent import detect_anomalies

        content, artifact = detect_anomalies.func(
            data_raw=bike_df.to_dict(),
            method="IsolationForest",
            contamination=0.05,
        )

        assert artifact["n_anomalies"] > 0
        assert artifact["total_samples"] == len(bike_df)

    def test_detect_anomalies_top_anomalies_shape(self, churn_numeric_df):
        """top_anomalies contains at most 20 records and includes __anomaly_score__."""
        from ai_data_science_team.agents.anomaly_detection_agent import detect_anomalies

        _, artifact = detect_anomalies.func(
            data_raw=churn_numeric_df.to_dict(),
            method="IsolationForest",
            contamination=0.10,
        )

        top = artifact["top_anomalies"]
        assert isinstance(top, list)
        assert len(top) <= 20
        if top:
            assert "__anomaly_score__" in top[0]

    def test_get_anomaly_params_tool(self):
        """get_anomaly_params returns human-readable param string."""
        from ai_data_science_team.agents.anomaly_detection_agent import get_anomaly_params

        result = get_anomaly_params.func(method="LOF", contamination=0.08)

        assert isinstance(result, str)
        assert "LOF" in result
        assert "0.08" in result


class TestModelExplainabilityToolUnit:
    """Call SHAP/LIME tool functions directly (no LLM)."""

    def test_explain_with_shap_returns_importance(self, churn_model_data):
        """SHAP tool returns feature_importance dict with correct keys."""
        from ai_data_science_team.agents.model_explainability_agent import explain_with_shap

        md = churn_model_data
        content, artifact = explain_with_shap.func(
            model_artifact=md["model"],
            data_raw=md["X_test"].to_dict(),
            background_data_raw=md["X_train"].to_dict(),
            n_samples=50,
        )

        assert isinstance(content, str)
        assert "SHAP" in content
        assert "feature_importance" in artifact
        fi = artifact["feature_importance"]
        assert isinstance(fi, dict)
        assert set(fi.keys()) == set(md["feature_names"])
        # All importances are non-negative floats
        assert all(isinstance(v, float) and v >= 0 for v in fi.values())

    def test_explain_with_shap_top_features(self, churn_model_data):
        """top_features is sorted descending by importance."""
        from ai_data_science_team.agents.model_explainability_agent import explain_with_shap

        md = churn_model_data
        _, artifact = explain_with_shap.func(
            model_artifact=md["model"],
            data_raw=md["X_test"].to_dict(),
            background_data_raw=md["X_train"].to_dict(),
            n_samples=30,
        )

        top = artifact["top_features"]
        assert isinstance(top, list)
        assert len(top) <= len(md["feature_names"])
        # Verify descending sort
        vals = [v for _, v in top]
        assert vals == sorted(vals, reverse=True)

    def test_explain_with_lime_returns_explanation(self, churn_model_data):
        """LIME tool returns a non-empty explanation list for sample_index=0."""
        from ai_data_science_team.agents.model_explainability_agent import explain_with_lime

        md = churn_model_data
        content, artifact = explain_with_lime.func(
            model_artifact=md["model"],
            data_raw=md["X_test"].to_dict(),
            background_data_raw=md["X_train"].to_dict(),
            sample_index=0,
        )

        assert isinstance(content, str)
        assert "LIME" in content
        assert "lime_explanation" in artifact
        lime_exp = artifact["lime_explanation"]
        assert isinstance(lime_exp, list)
        assert len(lime_exp) > 0
        # Each item should be a (feature_condition_str, float_weight) tuple
        assert all(isinstance(item, (list, tuple)) and len(item) == 2 for item in lime_exp)

    def test_explain_with_lime_sample_index_clamp(self, churn_model_data):
        """sample_index > dataset length is clamped to last valid index."""
        from ai_data_science_team.agents.model_explainability_agent import explain_with_lime

        md = churn_model_data
        big_index = 99999
        content, artifact = explain_with_lime.func(
            model_artifact=md["model"],
            data_raw=md["X_test"].head(5).to_dict(),
            background_data_raw=md["X_train"].to_dict(),
            sample_index=big_index,
        )

        # Should not raise; sample_index is silently clamped
        assert artifact["sample_index"] == 4  # len=5, last valid = 4

    def test_get_explainability_params_tool(self):
        """get_explainability_params returns config string."""
        from ai_data_science_team.agents.model_explainability_agent import get_explainability_params

        result = get_explainability_params.func(n_samples=75)

        assert isinstance(result, str)
        assert "75" in result


# ===========================================================================
# TG2 — Integration tests (real gpt-4o-mini)
# ===========================================================================


@pytest.mark.integration
class TestAnomalyDetectionIntegration:
    """AnomalyDetectionAgent with real LLM."""

    @skip_no_key
    def test_invoke_isolation_forest(self, llm, churn_numeric_df):
        """Agent detects anomalies with IsolationForest and fills response."""
        from ai_data_science_team.agents.anomaly_detection_agent import AnomalyDetectionAgent

        agent = AnomalyDetectionAgent(model=llm, method="IsolationForest", contamination=0.05)
        _invoke_safe(agent, data_raw=churn_numeric_df)

        assert agent.response is not None
        assert agent.get_n_anomalies() is not None
        assert agent.get_n_anomalies() > 0

    @skip_no_key
    def test_invoke_autoensemble_bike(self, llm, bike_df):
        """Agent works on bike sales data with AutoEnsemble."""
        from ai_data_science_team.agents.anomaly_detection_agent import AnomalyDetectionAgent

        agent = AnomalyDetectionAgent(model=llm, method="AutoEnsemble", contamination=0.05)
        _invoke_safe(agent, data_raw=bike_df)

        assert agent.get_anomaly_result() is not None

    @skip_no_key
    def test_getter_methods(self, llm, churn_numeric_df):
        """All getters return expected types after invocation."""
        from ai_data_science_team.agents.anomaly_detection_agent import AnomalyDetectionAgent

        agent = AnomalyDetectionAgent(model=llm, method="IsolationForest", contamination=0.05)
        _invoke_safe(agent, data_raw=churn_numeric_df)

        indices = agent.get_anomaly_indices()
        rate = agent.get_anomaly_rate()
        scores = agent.get_anomaly_scores()
        top = agent.get_top_anomalies()
        ai_msg = agent.get_ai_message()

        assert isinstance(indices, list)
        assert isinstance(rate, float)
        assert isinstance(scores, list)
        assert isinstance(top, pd.DataFrame)
        assert isinstance(ai_msg, str)
        assert len(ai_msg) > 0

    @skip_no_key
    def test_update_params_rebuilds_graph(self, llm, churn_numeric_df):
        """update_params() changes method and rebuildsgraph without error."""
        from ai_data_science_team.agents.anomaly_detection_agent import AnomalyDetectionAgent

        agent = AnomalyDetectionAgent(model=llm, method="IsolationForest")
        agent.update_params(method="LOF", contamination=0.07)

        assert agent._params["method"] == "LOF"
        assert agent._params["contamination"] == 0.07

        _invoke_safe(agent, data_raw=churn_numeric_df)
        # After update the graph ran with the new method
        result = agent.get_anomaly_result()
        assert result is not None


@pytest.mark.integration
class TestModelExplainabilityIntegration:
    """ModelExplainabilityAgent with real LLM."""

    @skip_no_key
    def test_invoke_shap(self, llm, churn_model_data):
        """Agent runs SHAP explanation and returns feature importance."""
        from ai_data_science_team.agents.model_explainability_agent import ModelExplainabilityAgent

        md = churn_model_data
        agent = ModelExplainabilityAgent(model=llm, n_samples=50)
        _invoke_safe(
            agent,
            model_artifact=md["model"],
            background_data=md["X_train"],
            explain_data=md["X_test"],
        )

        importance = agent.get_shap_importance()
        assert isinstance(importance, dict)
        assert len(importance) == len(md["feature_names"])

    @skip_no_key
    def test_invoke_shap_top_feature(self, llm, churn_model_data):
        """get_top_feature() returns a string (feature name)."""
        from ai_data_science_team.agents.model_explainability_agent import ModelExplainabilityAgent

        md = churn_model_data
        agent = ModelExplainabilityAgent(model=llm, n_samples=50)
        _invoke_safe(
            agent,
            model_artifact=md["model"],
            background_data=md["X_train"],
            explain_data=md["X_test"],
        )

        top = agent.get_top_feature()
        assert isinstance(top, str)
        assert top in md["feature_names"]

    @skip_no_key
    def test_ai_message_non_empty(self, llm, churn_model_data):
        """get_ai_message() returns a non-empty string."""
        from ai_data_science_team.agents.model_explainability_agent import ModelExplainabilityAgent

        md = churn_model_data
        agent = ModelExplainabilityAgent(model=llm, n_samples=30)
        _invoke_safe(
            agent,
            model_artifact=md["model"],
            background_data=md["X_train"],
            explain_data=md["X_test"],
        )

        ai_msg = agent.get_ai_message()
        assert isinstance(ai_msg, str) and len(ai_msg) > 0

    @skip_no_key
    def test_update_params_n_samples(self, llm, churn_model_data):
        """update_params changes n_samples and agent still works."""
        from ai_data_science_team.agents.model_explainability_agent import ModelExplainabilityAgent

        md = churn_model_data
        agent = ModelExplainabilityAgent(model=llm, n_samples=200)
        agent.update_params(n_samples=10)

        assert agent._params["n_samples"] == 10

        _invoke_safe(
            agent,
            model_artifact=md["model"],
            background_data=md["X_train"],
            explain_data=md["X_test"].head(10),
        )
        assert agent.get_explanation() is not None


# ===========================================================================
# TG3 — E2E tests
# ===========================================================================


@pytest.mark.e2e
class TestM23E2E:
    """End-to-end M23 pipeline tests."""

    def test_imports_from_agents_init(self):
        """AnomalyDetectionAgent and ModelExplainabilityAgent import from top-level agents."""
        from ai_data_science_team.agents import AnomalyDetectionAgent, ModelExplainabilityAgent

        assert AnomalyDetectionAgent is not None
        assert ModelExplainabilityAgent is not None

    def test_make_factory_functions_importable(self):
        """Factory functions are importable from agents package."""
        from ai_data_science_team.agents import (
            make_anomaly_detection_agent,
            make_model_explainability_agent,
        )

        assert callable(make_anomaly_detection_agent)
        assert callable(make_model_explainability_agent)

    @skip_no_key
    def test_anomaly_then_explainability_pipeline(self, llm, churn_numeric_df, churn_model_data):
        """Detect anomalies → explain model → verify consistent results.

        This mimics a real-world workflow:
        1. Detect anomalies in churn feature data.
        2. Build a classifier on clean data.
        3. Explain the classifier with SHAP.
        """
        from ai_data_science_team.agents.anomaly_detection_agent import AnomalyDetectionAgent
        from ai_data_science_team.agents.model_explainability_agent import ModelExplainabilityAgent

        # Step 1: anomaly detection
        anom_agent = AnomalyDetectionAgent(model=llm, method="IsolationForest", contamination=0.05)
        _invoke_safe(anom_agent, data_raw=churn_numeric_df)

        anomaly_indices = anom_agent.get_anomaly_indices()
        assert isinstance(anomaly_indices, list)

        # Step 2: model explainability on the classifier
        md = churn_model_data
        expl_agent = ModelExplainabilityAgent(model=llm, n_samples=50)
        _invoke_safe(
            expl_agent,
            model_artifact=md["model"],
            background_data=md["X_train"],
            explain_data=md["X_test"],
        )

        importance = expl_agent.get_shap_importance()
        assert isinstance(importance, dict)
        # Top feature must be one of the known columns
        top = expl_agent.get_top_feature()
        assert top in md["feature_names"]

        # Step 3: confirm tool_calls are populated for both agents
        assert anom_agent.get_tool_calls()
        assert expl_agent.get_tool_calls()
