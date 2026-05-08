"""TG1 / TG2 / TG3 — Tests for M24 Data Quality & Model Monitoring Agents.

Test Groups
-----------
TG1 (unit tests, no LLM required):
    * DataQualityAgent tools via .func() — profile_data_quality, validate_schema, params (6 tests)
    * ModelMonitoringAgent tools via .func() — detect_drift, compute_performance, params (6 tests)

TG2 (integration tests, real gpt-4o-mini):
    * DataQualityAgent.invoke_agent() end-to-end (4 tests)
    * ModelMonitoringAgent.invoke_agent() end-to-end (4 tests)

TG3 (e2e tests):
    * Import check from agents.__init__ (1 test, no LLM)
    * Factory functions importable (1 test, no LLM)
    * Full data quality → model monitoring pipeline (1 test, no LLM)

Run all:
    pytest tests/test_m24_agents.py -v

Skip LLM tests:
    pytest tests/test_m24_agents.py -v -m "not integration and not e2e"

Run only integration:
    pytest tests/test_m24_agents.py -v -m integration
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Markers / skip helpers
# ---------------------------------------------------------------------------
pytestmark = pytest.mark.m24

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
skip_no_key = pytest.mark.skipif(
    not OPENAI_API_KEY,
    reason="OPENAI_API_KEY is not set — skipping LLM-dependent test",
)

langchain_openai = pytest.importorskip(
    "langchain_openai",
    reason="langchain_openai is not installed — skipping M24 tests",
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
def churn_numeric_df(churn_df: pd.DataFrame) -> pd.DataFrame:
    """Numeric feature columns from churn data."""
    df = churn_df.copy()
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")
    return df[["tenure", "MonthlyCharges", "TotalCharges"]].fillna(0).astype(float)


@pytest.fixture(scope="session")
def reference_df(churn_numeric_df: pd.DataFrame) -> pd.DataFrame:
    """First 50% of churn numeric data as reference dataset."""
    mid = len(churn_numeric_df) // 2
    return churn_numeric_df.iloc[:mid].reset_index(drop=True)


@pytest.fixture(scope="session")
def current_df(churn_numeric_df: pd.DataFrame) -> pd.DataFrame:
    """Second 50% of churn numeric data as current dataset (slight drift expected)."""
    mid = len(churn_numeric_df) // 2
    return churn_numeric_df.iloc[mid:].reset_index(drop=True)


@pytest.fixture(scope="session")
def classification_data(churn_df: pd.DataFrame) -> Dict[str, Any]:
    """Train a RF classifier; return y_true, y_pred, baseline_metrics."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, f1_score
    from sklearn.model_selection import train_test_split

    df = churn_df.copy()
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce").fillna(0)
    df["Churn"] = (df["Churn"].astype(str).str.lower().isin(["yes", "1"])).astype(int)
    X = df[["tenure", "MonthlyCharges", "TotalCharges"]].fillna(0)
    y = df["Churn"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42
    )
    clf = RandomForestClassifier(n_estimators=20, random_state=42)
    clf.fit(X_train, y_train)
    y_pred = clf.predict(X_test)

    return {
        "y_true": pd.Series(y_test.values, name="Churn"),
        "y_pred": pd.Series(y_pred, name="Churn_pred"),
        "baseline": {
            "accuracy": round(accuracy_score(y_test, y_pred) - 0.05, 6),  # artificially lower baseline
            "f1_weighted": round(f1_score(y_test, y_pred, average="weighted") - 0.05, 6),
        },
    }


@pytest.fixture(scope="session")
def llm():
    """Real gpt-4o-mini LLM for integration tests."""
    if not OPENAI_API_KEY:
        pytest.skip("OPENAI_API_KEY is not set — skipping LLM fixture")
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model="gpt-4o-mini", temperature=0)


def _invoke_safe(agent, **kw):
    """invoke_agent; skip on quota errors."""
    try:
        return agent.invoke_agent(**kw)
    except Exception as exc:
        err = str(exc)
        if any(x in err for x in ("insufficient_quota", "RateLimitError", "rate_limit")):
            pytest.skip("OpenAI quota exceeded")
        raise


# ===========================================================================
# TG1 — Unit Tests (no LLM, direct tool calls)
# ===========================================================================


class TestDataQualityToolUnit:
    """Tests for DataQuality tools using .func() directly."""

    def test_profile_quality_basic(self, churn_numeric_df: pd.DataFrame):
        """profile_data_quality returns quality_score and completeness."""
        from ai_data_science_team.agents.data_quality_agent import profile_data_quality

        content, artifact = profile_data_quality.func(
            data_raw=churn_numeric_df.to_dict(),
            outlier_method="iqr",
            outlier_threshold=1.5,
        )
        assert isinstance(content, str)
        assert "quality" in content.lower() or "data" in content.lower()
        assert "quality_score" in artifact
        assert 0 <= artifact["quality_score"] <= 100
        assert "completeness" in artifact
        assert "n_rows" in artifact
        assert artifact["n_rows"] == len(churn_numeric_df)

    def test_profile_quality_zscore(self, churn_numeric_df: pd.DataFrame):
        """profile_data_quality works with zscore method."""
        from ai_data_science_team.agents.data_quality_agent import profile_data_quality

        _, artifact = profile_data_quality.func(
            data_raw=churn_numeric_df.to_dict(),
            outlier_method="zscore",
            outlier_threshold=3.0,
        )
        assert artifact["outlier_method"] == "zscore"
        assert "outlier_counts" in artifact

    def test_profile_quality_with_nulls(self):
        """profile_data_quality detects null rates correctly."""
        from ai_data_science_team.agents.data_quality_agent import profile_data_quality

        df = pd.DataFrame({"a": [1, 2, None, 4, 5], "b": [None, None, None, 4, 5]})
        _, artifact = profile_data_quality.func(
            data_raw=df.to_dict(),
            outlier_method="iqr",
            outlier_threshold=1.5,
        )
        assert artifact["null_rates"]["a"] == pytest.approx(0.2)
        assert artifact["null_rates"]["b"] == pytest.approx(0.6)
        assert artifact["mean_null_rate"] == pytest.approx(0.4)

    def test_validate_schema_pass(self, churn_numeric_df: pd.DataFrame):
        """validate_schema detects no violations when schema matches."""
        from ai_data_science_team.agents.data_quality_agent import validate_schema

        schema = {col: str(churn_numeric_df[col].dtype) for col in churn_numeric_df.columns}
        _, artifact = validate_schema.func(
            data_raw=churn_numeric_df.to_dict(),
            expected_schema=schema,
        )
        assert artifact["n_violations"] == 0
        assert artifact["missing_columns"] == []
        assert artifact["type_mismatches"] == []

    def test_validate_schema_missing_col(self, churn_numeric_df: pd.DataFrame):
        """validate_schema detects missing columns."""
        from ai_data_science_team.agents.data_quality_agent import validate_schema

        schema = {
            "tenure": "float64",
            "MonthlyCharges": "float64",
            "TotalCharges": "float64",
            "nonexistent_col": "int64",  # missing from data
        }
        _, artifact = validate_schema.func(
            data_raw=churn_numeric_df.to_dict(),
            expected_schema=schema,
        )
        assert "nonexistent_col" in artifact["missing_columns"]

    def test_get_data_quality_params_tool(self):
        """get_data_quality_params returns config string."""
        from ai_data_science_team.agents.data_quality_agent import get_data_quality_params

        result = get_data_quality_params.func(
            outlier_method="iqr",
            outlier_threshold=1.5,
        )
        assert "iqr" in result
        assert "1.5" in result


class TestModelMonitoringToolUnit:
    """Tests for ModelMonitoring tools using .func() directly."""

    def test_detect_drift_psi(self, reference_df: pd.DataFrame, current_df: pd.DataFrame):
        """detect_drift returns feature drift artifact using PSI."""
        from ai_data_science_team.agents.model_monitoring_agent import detect_drift

        content, artifact = detect_drift.func(
            reference_data_raw=reference_df.to_dict(),
            current_data_raw=current_df.to_dict(),
            drift_method="psi",
            psi_bins=10,
        )
        assert isinstance(content, str)
        assert "feature_drift" in artifact
        assert "overall_mean_psi" in artifact
        assert "overall_severity" in artifact
        assert artifact["overall_severity"] in ("stable", "moderate", "significant")
        assert artifact["n_features_checked"] == len(reference_df.columns)

    def test_detect_drift_ks(self, reference_df: pd.DataFrame, current_df: pd.DataFrame):
        """detect_drift works with KS test method."""
        from ai_data_science_team.agents.model_monitoring_agent import detect_drift

        _, artifact = detect_drift.func(
            reference_data_raw=reference_df.to_dict(),
            current_data_raw=current_df.to_dict(),
            drift_method="ks",
            psi_bins=10,
        )
        # Each numeric feature should have ks_statistic
        for feat in artifact["feature_drift"]:
            if feat["is_numeric"]:
                assert "ks_statistic" in feat

    def test_detect_drift_both(self, reference_df: pd.DataFrame, current_df: pd.DataFrame):
        """detect_drift with 'both' includes PSI and KS results."""
        from ai_data_science_team.agents.model_monitoring_agent import detect_drift

        _, artifact = detect_drift.func(
            reference_data_raw=reference_df.to_dict(),
            current_data_raw=current_df.to_dict(),
            drift_method="both",
            psi_bins=10,
        )
        for feat in artifact["feature_drift"]:
            if feat["is_numeric"]:
                assert "psi" in feat
                assert "ks_statistic" in feat

    def test_compute_performance_classification(
        self, classification_data: Dict[str, Any]
    ):
        """compute_performance returns accuracy and f1 for classification."""
        from ai_data_science_team.agents.model_monitoring_agent import compute_performance

        y_true = classification_data["y_true"]
        y_pred = classification_data["y_pred"]

        content, artifact = compute_performance.func(
            y_true_raw=y_true.to_frame().to_dict(),
            y_pred_raw=y_pred.to_frame().to_dict(),
            task_type="classification",
            baseline_metrics={},
        )
        assert "accuracy" in artifact["metrics"]
        assert "f1_weighted" in artifact["metrics"]
        assert 0 <= artifact["metrics"]["accuracy"] <= 1.0

    def test_compute_performance_with_baseline(
        self, classification_data: Dict[str, Any]
    ):
        """compute_performance detects degradation vs lower baseline."""
        from ai_data_science_team.agents.model_monitoring_agent import compute_performance

        y_true = classification_data["y_true"]
        y_pred = classification_data["y_pred"]
        baseline = classification_data["baseline"]  # artificially lower

        _, artifact = compute_performance.func(
            y_true_raw=y_true.to_frame().to_dict(),
            y_pred_raw=y_pred.to_frame().to_dict(),
            task_type="classification",
            baseline_metrics=baseline,
        )
        # Current metrics are higher than baseline so no degradation
        assert "degradation" in artifact
        # has_degradation should be False (current > baseline)
        assert artifact.get("has_degradation") is False

    def test_get_monitoring_params_tool(self):
        """get_monitoring_params returns config string."""
        from ai_data_science_team.agents.model_monitoring_agent import get_monitoring_params

        result = get_monitoring_params.func(
            drift_method="both",
            psi_bins=10,
            task_type="classification",
        )
        assert "both" in result
        assert "classification" in result


# ===========================================================================
# TG2 — Integration Tests (real gpt-4o-mini)
# ===========================================================================


@pytest.mark.integration
class TestDataQualityIntegration:
    """Integration tests for DataQualityAgent.invoke_agent()."""

    @skip_no_key
    def test_invoke_quality_churn(self, llm, churn_numeric_df: pd.DataFrame):
        """invoke_agent produces quality_score on churn data."""
        from ai_data_science_team.agents.data_quality_agent import DataQualityAgent

        agent = DataQualityAgent(model=llm)
        _invoke_safe(agent, data_raw=churn_numeric_df)
        assert agent.response is not None
        score = agent.get_quality_score()
        assert score is not None
        assert 0 <= score <= 100

    @skip_no_key
    def test_invoke_quality_bike(self, llm, bike_df: pd.DataFrame):
        """invoke_agent produces quality_score on bike data."""
        from ai_data_science_team.agents.data_quality_agent import DataQualityAgent

        agent = DataQualityAgent(model=llm)
        _invoke_safe(agent, data_raw=bike_df)
        assert agent.get_quality_score() is not None

    @skip_no_key
    def test_getter_null_rates(self, llm, churn_numeric_df: pd.DataFrame):
        """get_null_rates returns dict after invoke."""
        from ai_data_science_team.agents.data_quality_agent import DataQualityAgent

        agent = DataQualityAgent(model=llm)
        _invoke_safe(agent, data_raw=churn_numeric_df)
        null_rates = agent.get_null_rates()
        assert null_rates is not None
        assert isinstance(null_rates, dict)

    @skip_no_key
    def test_update_params_rebuilds(self, llm, churn_numeric_df: pd.DataFrame):
        """update_params changes method and agent still runs."""
        from ai_data_science_team.agents.data_quality_agent import DataQualityAgent

        agent = DataQualityAgent(model=llm, outlier_method="iqr")
        agent.update_params(outlier_method="zscore", outlier_threshold=3.0)
        assert agent._params["outlier_method"] == "zscore"
        _invoke_safe(agent, data_raw=churn_numeric_df)
        score = agent.get_quality_score()
        assert score is not None


@pytest.mark.integration
class TestModelMonitoringIntegration:
    """Integration tests for ModelMonitoringAgent.invoke_agent()."""

    @skip_no_key
    def test_invoke_drift_psi(
        self, llm, reference_df: pd.DataFrame, current_df: pd.DataFrame
    ):
        """invoke_agent detects drift between reference and current data."""
        from ai_data_science_team.agents.model_monitoring_agent import ModelMonitoringAgent

        agent = ModelMonitoringAgent(model=llm, drift_method="psi")
        _invoke_safe(agent, reference_data=reference_df, current_data=current_df)
        assert agent.response is not None
        severity = agent.get_drift_severity()
        assert severity in ("stable", "moderate", "significant")

    @skip_no_key
    def test_invoke_drift_both_methods(
        self, llm, reference_df: pd.DataFrame, current_df: pd.DataFrame
    ):
        """invoke_agent with 'both' drift method works."""
        from ai_data_science_team.agents.model_monitoring_agent import ModelMonitoringAgent

        agent = ModelMonitoringAgent(model=llm, drift_method="both")
        _invoke_safe(agent, reference_data=reference_df, current_data=current_df)
        drift = agent.get_drift_report()
        assert drift is not None
        assert "feature_drift" in drift

    @skip_no_key
    def test_invoke_with_performance(
        self,
        llm,
        reference_df: pd.DataFrame,
        current_df: pd.DataFrame,
        classification_data: Dict[str, Any],
    ):
        """invoke_agent computes performance metrics when y_true/y_pred provided."""
        from ai_data_science_team.agents.model_monitoring_agent import ModelMonitoringAgent

        agent = ModelMonitoringAgent(
            model=llm,
            task_type="classification",
            baseline_metrics=classification_data["baseline"],
        )
        _invoke_safe(
            agent,
            reference_data=reference_df,
            current_data=current_df,
            y_true=classification_data["y_true"],
            y_pred=classification_data["y_pred"],
        )
        metrics = agent.get_performance_metrics()
        assert metrics is not None
        assert "accuracy" in metrics

    @skip_no_key
    def test_update_params_task_type(
        self, llm, reference_df: pd.DataFrame, current_df: pd.DataFrame
    ):
        """update_params changes drift_method successfully."""
        from ai_data_science_team.agents.model_monitoring_agent import ModelMonitoringAgent

        agent = ModelMonitoringAgent(model=llm, drift_method="psi")
        agent.update_params(drift_method="ks")
        assert agent._params["drift_method"] == "ks"
        _invoke_safe(agent, reference_data=reference_df, current_data=current_df)
        assert agent.response is not None


# ===========================================================================
# TG3 — E2E Tests
# ===========================================================================


@pytest.mark.e2e
class TestM24E2E:
    """E2E tests: import chains, factory functions, pipeline."""

    def test_imports_from_agents_init(self):
        """DataQualityAgent and ModelMonitoringAgent are importable from agents.__init__."""
        from ai_data_science_team.agents import DataQualityAgent, ModelMonitoringAgent

        assert DataQualityAgent is not None
        assert ModelMonitoringAgent is not None

    def test_make_factory_functions_importable(self):
        """Factory functions are importable from agents.__init__."""
        from ai_data_science_team.agents import (
            make_data_quality_agent,
            make_model_monitoring_agent,
        )

        assert callable(make_data_quality_agent)
        assert callable(make_model_monitoring_agent)

    def test_quality_then_monitoring_pipeline(
        self,
        churn_numeric_df: pd.DataFrame,
        reference_df: pd.DataFrame,
        current_df: pd.DataFrame,
        classification_data: Dict[str, Any],
    ):
        """No-LLM pipeline test: run tools directly and verify artifact chain."""
        from ai_data_science_team.agents.data_quality_agent import profile_data_quality
        from ai_data_science_team.agents.model_monitoring_agent import (
            compute_performance,
            detect_drift,
        )

        # Step 1: Data quality profile
        _, quality_art = profile_data_quality.func(
            data_raw=churn_numeric_df.to_dict(),
            outlier_method="iqr",
            outlier_threshold=1.5,
        )
        assert quality_art["quality_score"] > 0

        # Step 2: Drift detection on reference vs current
        _, drift_art = detect_drift.func(
            reference_data_raw=reference_df.to_dict(),
            current_data_raw=current_df.to_dict(),
            drift_method="psi",
            psi_bins=10,
        )
        assert "feature_drift" in drift_art
        assert drift_art["n_features_checked"] == 3

        # Step 3: Performance metrics
        _, perf_art = compute_performance.func(
            y_true_raw=classification_data["y_true"].to_frame().to_dict(),
            y_pred_raw=classification_data["y_pred"].to_frame().to_dict(),
            task_type="classification",
            baseline_metrics=classification_data["baseline"],
        )
        assert "accuracy" in perf_art["metrics"]

        # Verify chain produces consistent output types
        assert isinstance(quality_art["quality_score"], float)
        assert isinstance(drift_art["overall_mean_psi"], float)
        assert isinstance(perf_art["metrics"]["accuracy"], float)
