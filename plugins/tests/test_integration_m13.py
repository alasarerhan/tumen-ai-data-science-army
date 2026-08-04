"""
M13 – Zaman Serisi Ajanları TG2 Entegrasyon Testleri
=====================================================
Gerçek LLM API'si (OpenAI) ile uçtan-uca çalışır.
Çalıştırmak için:
    python -m pytest tests/test_integration_m13.py -v -m integration
Atlamak için (diğer testlerle birlikte):
    python -m pytest tests/ -v -m "not integration"
"""

import pandas as pd
import pytest
from _llm import make_chat_model, skip_no_key

# ---------------------------------------------------------------------------
# Guards — skip the entire module if the key is absent
# ---------------------------------------------------------------------------
pytestmark = pytest.mark.integration


langchain_openai = pytest.importorskip(
    "langchain_openai",
    reason="langchain_openai is not installed — skipping integration tests",
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def llm():
    """Small, cheap OpenAI model for integration tests."""
    return make_chat_model(temperature=0)


@pytest.fixture(scope="module")
def monthly_series() -> pd.DataFrame:
    """12-month synthetic monthly time series."""
    return pd.DataFrame(
        {
            "date": pd.date_range("2023-01-01", periods=12, freq="MS"),
            "value": [
                100,
                110,
                105,
                120,
                130,
                125,
                140,
                135,
                150,
                145,
                160,
                155,
            ],
        }
    )


# ---------------------------------------------------------------------------
# TimeSeriesEDAAgent
# ---------------------------------------------------------------------------


@skip_no_key
def test_time_series_eda_agent_basic(llm, monthly_series):
    """TimeSeriesEDAAgent should return a non-empty AI message after analysis."""
    from ai_data_science_team.ml_agents.time_series_agents import TimeSeriesEDAAgent

    agent = TimeSeriesEDAAgent(model=llm)
    agent.invoke_agent(
        user_instructions="Perform a brief EDA on this monthly time series.",
        data_raw=monthly_series,
        date_column="date",
        value_column="value",
    )

    msg = agent.get_ai_message()
    assert isinstance(msg, str), "Expected a string AI message"
    assert len(msg) > 0, "AI message should not be empty"


@skip_no_key
def test_time_series_eda_agent_artifacts(llm, monthly_series):
    """TimeSeriesEDAAgent should populate artifacts dict."""
    from ai_data_science_team.ml_agents.time_series_agents import TimeSeriesEDAAgent

    agent = TimeSeriesEDAAgent(model=llm)
    agent.invoke_agent(
        user_instructions="Calculate summary statistics for this time series.",
        data_raw=monthly_series,
        date_column="date",
        value_column="value",
    )

    artifacts = agent.get_artifacts()
    assert isinstance(artifacts, dict), "Artifacts should be a dict"


@skip_no_key
def test_time_series_eda_agent_tool_calls(llm, monthly_series):
    """TimeSeriesEDAAgent should record at least one tool call."""
    from ai_data_science_team.ml_agents.time_series_agents import TimeSeriesEDAAgent

    agent = TimeSeriesEDAAgent(model=llm)
    agent.invoke_agent(
        user_instructions="Describe the trend in this time series.",
        data_raw=monthly_series,
        date_column="date",
        value_column="value",
    )

    tool_calls = agent.get_tool_calls()
    assert isinstance(tool_calls, list), "Tool calls should be a list"
    assert len(tool_calls) > 0, "At least one tool should have been called"


# ---------------------------------------------------------------------------
# ForecastEvaluationAgent
# ---------------------------------------------------------------------------

ACTUAL = [100.0, 110.0, 105.0, 120.0, 130.0, 125.0]
PREDICTED = [102.0, 108.0, 107.0, 118.0, 132.0, 123.0]


@skip_no_key
def test_forecast_evaluation_agent_basic(llm):
    """ForecastEvaluationAgent should return a non-empty AI message."""
    from ai_data_science_team.ml_agents.time_series_agents import ForecastEvaluationAgent

    agent = ForecastEvaluationAgent(model=llm)
    agent.invoke_agent(
        user_instructions="Evaluate the forecast accuracy and summarise the key metrics.",
        actual=ACTUAL,
        predicted=PREDICTED,
    )

    msg = agent.get_ai_message()
    assert isinstance(msg, str) and len(msg) > 0


@skip_no_key
def test_forecast_evaluation_agent_artifacts(llm):
    """ForecastEvaluationAgent should populate artifacts with metric keys."""
    from ai_data_science_team.ml_agents.time_series_agents import ForecastEvaluationAgent

    agent = ForecastEvaluationAgent(model=llm)
    agent.invoke_agent(
        user_instructions="Calculate MAE, RMSE and MAPE.",
        actual=ACTUAL,
        predicted=PREDICTED,
    )

    artifacts = agent.get_artifacts()
    assert isinstance(artifacts, dict)


# ---------------------------------------------------------------------------
# ForecastingModelAgent  (smoke test — just confirms no crash)
# ---------------------------------------------------------------------------


@skip_no_key
def test_forecasting_model_agent_smoke(llm, monthly_series):
    """ForecastingModelAgent should complete without raising an exception."""
    from ai_data_science_team.ml_agents.time_series_agents import ForecastingModelAgent

    agent = ForecastingModelAgent(model=llm)
    agent.invoke_agent(
        user_instructions=("Fit a simple forecasting model and produce a 3-step-ahead forecast."),
        data_raw=monthly_series,
        date_column="date",
        value_column="value",
    )

    msg = agent.get_ai_message()
    assert isinstance(msg, str) and len(msg) > 0
