"""Tests for M13 — Time-Series tools and agents.

Tool tests run without a real LLM.
Agent construction / invoke tests use a deterministic FakeLLM mock so no
API key is needed.
"""
from __future__ import annotations

import math
import random
from typing import List

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Helpers — synthetic time series
# ---------------------------------------------------------------------------


def _make_trend_series(n: int = 60, noise: float = 2.0, seed: int = 42) -> List[float]:
    rng = random.Random(seed)
    return [10 + 0.3 * i + rng.gauss(0, noise) for i in range(n)]


def _make_seasonal_series(n: int = 120, period: int = 12, seed: int = 42) -> List[float]:
    rng = random.Random(seed)
    return [
        50 + 10 * math.sin(2 * math.pi * i / period) + rng.gauss(0, 1)
        for i in range(n)
    ]


def _make_stationary_series(n: int = 100, seed: int = 42) -> List[float]:
    rng = random.Random(seed)
    return [rng.gauss(0, 1) for _ in range(n)]


# ===========================================================================
# Tool tests — stationarity_test
# ===========================================================================


def test_stationarity_test_stationary_series():
    from ai_data_science_team.tools.time_series import stationarity_test

    data = _make_stationary_series(120)
    text, result = stationarity_test.func(
        data=data, series_name="white_noise", significance=0.05
    )
    assert result["n_observations"] == 120
    assert "adf" in result
    assert "kpss" in result
    assert "conclusion" in result
    assert isinstance(result["conclusion"]["stationary"], bool)
    assert "white_noise" in text


def test_stationarity_test_trending_series():
    from ai_data_science_team.tools.time_series import stationarity_test

    # A random walk (canonical unit-root / non-stationary process)
    rng = random.Random(42)
    data = [0.0]
    for _ in range(199):
        data.append(data[-1] + rng.gauss(0, 1))
    _, result = stationarity_test.func(data=data, series_name="random_walk")
    # ADF typically does NOT reject H0 for a random walk → non-stationary
    assert result["adf"]["is_stationary"] is False


def test_stationarity_test_result_keys():
    from ai_data_science_team.tools.time_series import stationarity_test

    _, result = stationarity_test.func(data=_make_stationary_series())
    for key in ("adf", "kpss", "conclusion", "n_observations", "series_name"):
        assert key in result


# ===========================================================================
# Tool tests — seasonal_decompose_ts
# ===========================================================================


def test_seasonal_decompose_returns_components():
    from ai_data_science_team.tools.time_series import seasonal_decompose_ts

    data = _make_seasonal_series(120, period=12)
    text, result = seasonal_decompose_ts.func(
        data=data, period=12, model="additive", series_name="monthly"
    )
    assert "trend" in result
    assert "seasonal" in result
    assert "residual" in result
    assert len(result["seasonal_values"]) == 120
    assert result["period"] == 12


def test_seasonal_decompose_seasonal_strength():
    from ai_data_science_team.tools.time_series import seasonal_decompose_ts

    data = _make_seasonal_series(240, period=12)
    _, result = seasonal_decompose_ts.func(data=data, period=12)
    # The synthetic series has strong seasonality
    assert result["seasonal"]["strength"] > 0.5


def test_seasonal_decompose_insufficient_data():
    from ai_data_science_team.tools.time_series import seasonal_decompose_ts

    text, result = seasonal_decompose_ts.func(data=[1.0, 2.0, 3.0], period=12)
    assert "insufficient_data" in str(result) or "Not enough" in text


# ===========================================================================
# Tool tests — autocorrelation_analysis
# ===========================================================================


def test_autocorrelation_returns_lags():
    from ai_data_science_team.tools.time_series import autocorrelation_analysis

    data = _make_stationary_series(100)
    _, result = autocorrelation_analysis.func(data=data, nlags=10)
    assert len(result["acf_values"]) == 11   # lag 0 .. 10
    assert len(result["pacf_values"]) == 11
    assert "suggested_arima" in result


def test_autocorrelation_significant_lags_format():
    from ai_data_science_team.tools.time_series import autocorrelation_analysis

    _, result = autocorrelation_analysis.func(data=_make_seasonal_series(120), nlags=15)
    assert isinstance(result["significant_acf_lags"], list)
    assert isinstance(result["significant_pacf_lags"], list)


# ===========================================================================
# Tool tests — train_arima
# ===========================================================================


def test_train_arima_returns_aic_bic():
    from ai_data_science_team.tools.time_series import train_arima

    data = _make_stationary_series(80)
    _, result = train_arima.func(
        data=data, order=[1, 0, 1], seasonal_order=[0, 0, 0, 0]
    )
    assert "aic" in result
    assert "bic" in result
    assert isinstance(result["aic"], float)


def test_train_arima_in_sample_metrics():
    from ai_data_science_team.tools.time_series import train_arima

    data = _make_trend_series(80)
    _, result = train_arima.func(data=data, order=[1, 1, 0])
    assert result["in_sample_rmse"] >= 0
    assert result["in_sample_mae"] >= 0


def test_train_arima_result_keys():
    from ai_data_science_team.tools.time_series import train_arima

    _, result = train_arima.func(data=_make_stationary_series(60))
    for k in ("model_type", "order", "aic", "bic", "in_sample_rmse", "in_sample_mae"):
        assert k in result


# ===========================================================================
# Tool tests — evaluate_forecast
# ===========================================================================


def test_evaluate_forecast_perfect_prediction():
    from ai_data_science_team.tools.time_series import evaluate_forecast

    vals = [float(i) for i in range(1, 21)]
    _, result = evaluate_forecast.func(actual=vals, predicted=vals)
    assert result["rmse"] == pytest.approx(0.0, abs=1e-9)
    assert result["mae"] == pytest.approx(0.0, abs=1e-9)
    assert result["mape_pct"] == pytest.approx(0.0, abs=1e-9)
    assert result["r2"] == pytest.approx(1.0, abs=1e-6)


def test_evaluate_forecast_known_offset():
    from ai_data_science_team.tools.time_series import evaluate_forecast

    actual = [10.0, 20.0, 30.0, 40.0]
    predicted = [12.0, 22.0, 32.0, 42.0]  # constant offset +2
    _, result = evaluate_forecast.func(actual=actual, predicted=predicted)
    assert result["rmse"] == pytest.approx(2.0, abs=1e-6)
    assert result["mae"] == pytest.approx(2.0, abs=1e-6)


def test_evaluate_forecast_length_mismatch():
    from ai_data_science_team.tools.time_series import evaluate_forecast

    _, result = evaluate_forecast.func(actual=[1.0, 2.0], predicted=[1.0])
    assert "error" in result


def test_evaluate_forecast_r2_negative_for_bad_model():
    from ai_data_science_team.tools.time_series import evaluate_forecast

    actual = [1.0, 2.0, 3.0, 4.0, 5.0]
    predicted = [5.0, 4.0, 3.0, 2.0, 1.0]  # inverted
    _, result = evaluate_forecast.func(actual=actual, predicted=predicted)
    assert result["r2"] < 0


def test_evaluate_forecast_directional_accuracy():
    from ai_data_science_team.tools.time_series import evaluate_forecast

    actual = [1.0, 3.0, 2.0, 5.0, 4.0]
    predicted = [1.5, 2.5, 1.5, 4.5, 3.5]  # same direction each step
    _, result = evaluate_forecast.func(actual=actual, predicted=predicted)
    assert result["directional_accuracy_pct"] == pytest.approx(100.0, abs=1e-6)


# ===========================================================================
# Agent construction tests (mock LLM — no API key needed)
# ===========================================================================


def _fake_llm():
    """Return a minimal stub that satisfies BaseAgent graph construction."""
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage as LCAIMessage
    from langchain_core.outputs import ChatGeneration, ChatResult

    class FakeChatModel(BaseChatModel):
        @property
        def _llm_type(self) -> str:
            return "fake"

        def _generate(self, messages, stop=None, _run_manager=None, **kw) -> ChatResult:
            return ChatResult(
                generations=[
                    ChatGeneration(
                        message=LCAIMessage(content="Analysis complete.")
                    )
                ]
            )

        def bind_tools(self, tools, **kw):
            return self

    return FakeChatModel()


def test_time_series_eda_agent_instantiation():
    from ai_data_science_team.ml_agents.time_series_agents import TimeSeriesEDAAgent

    agent = TimeSeriesEDAAgent(model=_fake_llm())
    assert hasattr(agent, "invoke_agent")
    assert hasattr(agent, "get_artifacts")
    assert hasattr(agent, "get_ai_message")


def test_forecasting_model_agent_instantiation():
    from ai_data_science_team.ml_agents.time_series_agents import ForecastingModelAgent

    agent = ForecastingModelAgent(model=_fake_llm())
    assert hasattr(agent, "invoke_agent")
    assert hasattr(agent, "get_artifacts")


def test_forecast_evaluation_agent_instantiation():
    from ai_data_science_team.ml_agents.time_series_agents import ForecastEvaluationAgent

    agent = ForecastEvaluationAgent(model=_fake_llm())
    assert hasattr(agent, "invoke_agent")
    assert hasattr(agent, "get_artifacts")


def test_agent_update_params():
    from ai_data_science_team.ml_agents.time_series_agents import TimeSeriesEDAAgent

    llm = _fake_llm()
    agent = TimeSeriesEDAAgent(model=llm)
    original_graph = agent._compiled_graph
    agent.update_params(log_tool_calls=False)
    assert agent._compiled_graph is not original_graph  # rebuilt


def test_forecast_evaluation_agent_accepts_lists():
    """ForecastEvaluationAgent.invoke_agent must accept actual/predicted lists."""
    from ai_data_science_team.ml_agents.time_series_agents import ForecastEvaluationAgent

    agent = ForecastEvaluationAgent(model=_fake_llm())
    assert agent is not None
    actual = [1.0, 2.0, 3.0]
    predicted = [1.1, 2.1, 3.1]
    df = pd.DataFrame({"actual": actual, "predicted": predicted})
    assert df.to_dict() is not None


# ===========================================================================
# Tool tests — auto_forecast
# ===========================================================================


def test_auto_forecast_returns_leaderboard():
    """auto_forecast must return a sorted leaderboard with at least 2 entries."""
    from ai_data_science_team.tools.time_series import auto_forecast

    data = _make_seasonal_series(96, period=12)
    _, result = auto_forecast.func(
        data=data, periods_ahead=12, freq="M", backend="statsmodels"
    )
    assert "leaderboard" in result
    assert len(result["leaderboard"]) >= 2
    # Leaderboard must be sorted ascending by RMSE
    rmses = [r["rmse"] for r in result["leaderboard"]]
    assert rmses == sorted(rmses)


def test_auto_forecast_best_model_key():
    """auto_forecast result must include best_model and forecast keys."""
    from ai_data_science_team.tools.time_series import auto_forecast

    data = _make_stationary_series(80)
    _, result = auto_forecast.func(
        data=data, periods_ahead=6, freq="M", backend="statsmodels"
    )
    for k in ("best_model", "best_model_test_rmse", "best_model_test_mae", "forecast"):
        assert k in result, f"Missing key: {k}"
    assert len(result["forecast"]) == 6


def test_auto_forecast_forecast_length():
    """Forecast list must have exactly periods_ahead elements."""
    from ai_data_science_team.tools.time_series import auto_forecast

    data = _make_trend_series(60)
    _, result = auto_forecast.func(
        data=data, periods_ahead=8, freq="M", backend="statsmodels"
    )
    assert len(result["forecast"]) == 8


def test_auto_forecast_short_series_returns_error():
    """Series shorter than 10 observations must return an error dict."""
    from ai_data_science_team.tools.time_series import auto_forecast

    _, result = auto_forecast.func(
        data=[1.0, 2.0, 3.0], periods_ahead=3, freq="M", backend="statsmodels"
    )
    assert "error" in result


def test_auto_forecast_backend_key():
    """Result must report which backend was used."""
    from ai_data_science_team.tools.time_series import auto_forecast

    data = _make_seasonal_series(72)
    _, result = auto_forecast.func(
        data=data, periods_ahead=6, freq="M", backend="statsmodels"
    )
    assert result["backend"] == "statsmodels"


def test_auto_forecast_leaderboard_rmse_positive():
    """All leaderboard RMSE values must be non-negative finite numbers."""
    from ai_data_science_team.tools.time_series import auto_forecast

    data = _make_seasonal_series(60)
    _, result = auto_forecast.func(
        data=data, periods_ahead=6, freq="M", backend="statsmodels"
    )
    for entry in result["leaderboard"]:
        assert entry["rmse"] >= 0
        assert math.isfinite(entry["rmse"])


# ===========================================================================
# Agent construction tests — AutoForecastAgent
# ===========================================================================


def test_auto_forecast_agent_instantiation():
    from ai_data_science_team.ml_agents.time_series_agents import AutoForecastAgent

    agent = AutoForecastAgent(model=_fake_llm())
    assert hasattr(agent, "invoke_agent")
    assert hasattr(agent, "get_artifacts")
    assert hasattr(agent, "get_ai_message")


def test_auto_forecast_agent_update_params():
    from ai_data_science_team.ml_agents.time_series_agents import AutoForecastAgent

    agent = AutoForecastAgent(model=_fake_llm())
    original_graph = agent._compiled_graph
    agent.update_params(log_tool_calls=False)
    assert agent._compiled_graph is not original_graph
