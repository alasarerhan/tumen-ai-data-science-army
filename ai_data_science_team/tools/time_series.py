"""Time-series analysis and forecasting tools (M13).

All tools use *lazy imports* so that heavy optional dependencies
(statsmodels, prophet, sklearn, statsforecast) do not break the import chain
when they are not installed.  Each tool function raises an ``ImportError`` with
a clear install command if the dependency is missing.

Available tools
---------------
stationarity_test          ADF + KPSS unit-root tests.
seasonal_decompose_ts      STL decomposition → trend / seasonal / residual.
autocorrelation_analysis   ACF and PACF summary statistics.
train_arima                Fit a SARIMAX model and return artefacts.
train_prophet              Fit a Prophet model and return artefacts.
auto_forecast              AutoML — races AutoARIMA, AutoETS, AutoTheta, CES,
                            SeasonalNaive and Naive; selects the winner by
                            walk-forward RMSE.  Uses *statsforecast* (Nixtla)
                            when installed, falls back to statsmodels otherwise.
evaluate_forecast          Compute MAPE / RMSE / MAE / R2 for a forecast.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from langchain.tools import tool


# ---------------------------------------------------------------------------
# Stationarity test (ADF + KPSS)
# ---------------------------------------------------------------------------


@tool(response_format="content_and_artifact")
def stationarity_test(
    data: List[float],
    series_name: str = "series",
    significance: float = 0.05,
) -> tuple[str, Dict[str, Any]]:
    """Run Augmented Dickey-Fuller and KPSS unit-root tests on a numeric series.

    Parameters
    ----------
    data: List of numeric values (the time series values in chronological order).
    series_name: Label for the series (used in the output summary).
    significance: Significance level for reject/accept decision (default 0.05).

    Returns a text summary and a dict with test statistics, p-values, and
    a "stationary" boolean conclusion.
    """
    try:
        from statsmodels.tsa.stattools import adfuller, kpss
    except ImportError:
        msg = (
            "statsmodels is required for stationarity_test. "
            "Install it with: pip install statsmodels"
        )
        raise ImportError(msg)

    s = pd.Series(data, name=series_name).dropna()

    # ADF: H0 = unit root (non-stationary); reject H0 → stationary
    adf_stat, adf_p, _, _, adf_crit, _ = adfuller(s, autolag="AIC")
    adf_stationary = bool(adf_p < significance)

    # KPSS: H0 = stationary; reject H0 → non-stationary
    kpss_stat, kpss_p, _, kpss_crit = kpss(s, regression="c", nlags="auto")
    kpss_stationary = bool(kpss_p > significance)

    # Combined verdict
    stationary = adf_stationary and kpss_stationary

    result: Dict[str, Any] = {
        "series_name": series_name,
        "n_observations": len(s),
        "adf": {
            "statistic": round(adf_stat, 4),
            "p_value": round(adf_p, 4),
            "critical_values": {k: round(v, 4) for k, v in adf_crit.items()},
            "is_stationary": adf_stationary,
        },
        "kpss": {
            "statistic": round(kpss_stat, 4),
            "p_value": round(kpss_p, 4),
            "critical_values": {k: round(v, 4) for k, v in kpss_crit.items()},
            "is_stationary": kpss_stationary,
        },
        "conclusion": {
            "stationary": stationary,
            "recommendation": (
                "Series appears stationary — no differencing needed."
                if stationary
                else "Series appears non-stationary — consider differencing (d≥1) or transformation."
            ),
        },
    }

    text = (
        f"Stationarity test for '{series_name}' (n={len(s)}):\n"
        f"  ADF p={adf_p:.4f} → {'stationary' if adf_stationary else 'non-stationary'}\n"
        f"  KPSS p={kpss_p:.4f} → {'stationary' if kpss_stationary else 'non-stationary'}\n"
        f"  Verdict: {'✓ Stationary' if stationary else '✗ Non-stationary'}\n"
        f"  {result['conclusion']['recommendation']}"
    )
    return text, result


# ---------------------------------------------------------------------------
# Seasonal decomposition
# ---------------------------------------------------------------------------


@tool(response_format="content_and_artifact")
def seasonal_decompose_ts(
    data: List[float],
    period: int = 12,
    model: str = "additive",
    series_name: str = "series",
) -> tuple[str, Dict[str, Any]]:
    """Decompose a time series into trend, seasonal, and residual components.

    Parameters
    ----------
    data: Numeric values in chronological order.
    period: Seasonality period (e.g. 12 for monthly data with annual cycle,
            7 for daily data with weekly cycle).
    model: "additive" or "multiplicative".
    series_name: Label for the series.

    Returns a text summary + dict with trend/seasonal/residual stats.
    """
    try:
        from statsmodels.tsa.seasonal import seasonal_decompose as sm_decompose
    except ImportError:
        raise ImportError(
            "statsmodels is required. Install with: pip install statsmodels"
        )

    s = pd.Series(data, name=series_name).dropna()
    if len(s) < 2 * period:
        return (
            f"Not enough data for decomposition (need at least {2 * period} points, got {len(s)}).",
            {"error": "insufficient_data"},
        )

    dec = sm_decompose(s, model=model, period=period)

    trend_strength = float(
        1 - dec.resid.dropna().var() / (dec.trend.dropna() + dec.resid.dropna()).var()
    )
    seasonal_strength = float(
        1 - dec.resid.dropna().var() / (dec.seasonal.dropna() + dec.resid.dropna()).var()
    )

    result: Dict[str, Any] = {
        "series_name": series_name,
        "model": model,
        "period": period,
        "n_observations": len(s),
        "trend": {
            "mean": round(float(dec.trend.dropna().mean()), 4),
            "std": round(float(dec.trend.dropna().std()), 4),
            "strength": round(max(0.0, trend_strength), 4),
        },
        "seasonal": {
            "mean": round(float(dec.seasonal.mean()), 4),
            "std": round(float(dec.seasonal.std()), 4),
            "strength": round(max(0.0, seasonal_strength), 4),
        },
        "residual": {
            "mean": round(float(dec.resid.dropna().mean()), 4),
            "std": round(float(dec.resid.dropna().std()), 4),
        },
        "seasonal_values": dec.seasonal.tolist(),
        "trend_values": dec.trend.tolist(),
    }

    text = (
        f"Seasonal decomposition of '{series_name}' (period={period}, model={model}):\n"
        f"  Trend strength  : {result['trend']['strength']:.3f}  "
        f"({'strong' if result['trend']['strength'] > 0.6 else 'weak'})\n"
        f"  Seasonal strength: {result['seasonal']['strength']:.3f}  "
        f"({'strong' if result['seasonal']['strength'] > 0.6 else 'weak'})\n"
        f"  Residual std    : {result['residual']['std']:.4f}"
    )
    return text, result


# ---------------------------------------------------------------------------
# Autocorrelation analysis
# ---------------------------------------------------------------------------


@tool(response_format="content_and_artifact")
def autocorrelation_analysis(
    data: List[float],
    nlags: int = 20,
    series_name: str = "series",
) -> tuple[str, Dict[str, Any]]:
    """Compute ACF and PACF statistics to guide ARIMA order selection.

    Parameters
    ----------
    data: Numeric values in chronological order.
    nlags: Number of lags to compute (default 20).
    series_name: Label for the series.

    Returns dominant lag information and stationarity cues.
    """
    try:
        from statsmodels.tsa.stattools import acf, pacf
    except ImportError:
        raise ImportError(
            "statsmodels is required. Install with: pip install statsmodels"
        )

    s = pd.Series(data, name=series_name).dropna()
    actual_nlags = min(nlags, len(s) // 2 - 1)

    acf_vals = acf(s, nlags=actual_nlags, fft=True).tolist()
    pacf_vals = pacf(s, nlags=actual_nlags).tolist()

    # Simple heuristic: lags with |acf| > 2/sqrt(n) are significant
    threshold = 2.0 / (len(s) ** 0.5)
    significant_acf = [i for i, v in enumerate(acf_vals) if abs(v) > threshold and i > 0]
    significant_pacf = [i for i, v in enumerate(pacf_vals) if abs(v) > threshold and i > 0]

    result: Dict[str, Any] = {
        "series_name": series_name,
        "n_observations": len(s),
        "nlags_computed": actual_nlags,
        "significance_threshold": round(threshold, 4),
        "acf_values": [round(v, 4) for v in acf_vals],
        "pacf_values": [round(v, 4) for v in pacf_vals],
        "significant_acf_lags": significant_acf[:10],
        "significant_pacf_lags": significant_pacf[:10],
        "suggested_arima": {
            "q_candidates": significant_acf[:3],
            "p_candidates": significant_pacf[:3],
        },
    }

    text = (
        f"Autocorrelation analysis for '{series_name}' (n={len(s)}, nlags={actual_nlags}):\n"
        f"  Significance threshold (2/√n): {threshold:.4f}\n"
        f"  Significant ACF lags  (q): {significant_acf[:5] or 'none'}\n"
        f"  Significant PACF lags (p): {significant_pacf[:5] or 'none'}\n"
        f"  ARIMA order suggestion: p ∈ {significant_pacf[:3]}, q ∈ {significant_acf[:3]}"
    )
    return text, result


# ---------------------------------------------------------------------------
# ARIMA training
# ---------------------------------------------------------------------------


@tool(response_format="content_and_artifact")
def train_arima(
    data: List[float],
    order: List[int] = [1, 1, 1],
    seasonal_order: List[int] = [0, 0, 0, 0],
    series_name: str = "series",
) -> tuple[str, Dict[str, Any]]:
    """Fit a SARIMAX model on a numeric series.

    Parameters
    ----------
    data: Numeric values in chronological order.
    order: (p, d, q) ARIMA order.
    seasonal_order: (P, D, Q, s) seasonal order.  Use [0,0,0,0] for no seasonality.
    series_name: Label for the series.

    Returns model summary statistics and in-sample fit metrics.
    """
    try:
        from statsmodels.tsa.statespace.sarimax import SARIMAX
    except ImportError:
        raise ImportError(
            "statsmodels is required. Install with: pip install statsmodels"
        )

    s = pd.Series(data, name=series_name).dropna()
    p, d, q = order[:3]
    P, D, Q, s_period = seasonal_order[:4] if len(seasonal_order) >= 4 else (0, 0, 0, 0)

    try:
        model = SARIMAX(
            s,
            order=(p, d, q),
            seasonal_order=(P, D, Q, s_period),
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        fitted = model.fit(disp=False, maxiter=200)
    except Exception as exc:
        return f"ARIMA fitting failed: {exc}", {"error": str(exc)}

    resid = fitted.resid.dropna()
    rmse = float((resid ** 2).mean() ** 0.5)
    mae = float(resid.abs().mean())

    result: Dict[str, Any] = {
        "series_name": series_name,
        "model_type": "SARIMAX",
        "order": list(order[:3]),
        "seasonal_order": list(seasonal_order[:4]) if len(seasonal_order) >= 4 else [0, 0, 0, 0],
        "n_observations": len(s),
        "aic": round(float(fitted.aic), 4),
        "bic": round(float(fitted.bic), 4),
        "in_sample_rmse": round(rmse, 4),
        "in_sample_mae": round(mae, 4),
        "params": {k: round(float(v), 6) for k, v in fitted.params.items()},
        # Serialise enough state for forecasting (not the full fitted object)
        "_fitted_values": fitted.fittedvalues.tolist(),
        "_resid": resid.tolist(),
    }

    text = (
        f"ARIMA({p},{d},{q}) fitted on '{series_name}' (n={len(s)}):\n"
        f"  AIC={result['aic']}, BIC={result['bic']}\n"
        f"  In-sample RMSE={result['in_sample_rmse']}, MAE={result['in_sample_mae']}"
    )
    return text, result


# ---------------------------------------------------------------------------
# Prophet training (optional dependency)
# ---------------------------------------------------------------------------


@tool(response_format="content_and_artifact")
def train_prophet(
    dates: List[str],
    values: List[float],
    periods_ahead: int = 12,
    freq: str = "M",
    series_name: str = "series",
) -> tuple[str, Dict[str, Any]]:
    """Fit a Prophet model and generate a forward forecast.

    Parameters
    ----------
    dates: ISO-format date strings (YYYY-MM-DD) aligned with values.
    values: Numeric target values.
    periods_ahead: Number of future periods to forecast.
    freq: Pandas frequency alias for future dates, e.g. "M", "D", "H".
    series_name: Label for the series.

    Requires: pip install prophet
    """
    try:
        from prophet import Prophet  # type: ignore[import]
    except ImportError:
        raise ImportError(
            "Prophet is required for train_prophet. "
            "Install it with: pip install prophet"
        )

    df = pd.DataFrame({"ds": pd.to_datetime(dates), "y": values}).dropna()

    try:
        m = Prophet(yearly_seasonality="auto", weekly_seasonality=False)
        m.fit(df)
        future = m.make_future_dataframe(periods=periods_ahead, freq=freq)
        forecast = m.predict(future)
    except Exception as exc:
        return f"Prophet fitting failed: {exc}", {"error": str(exc)}

    fcast_tail = forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].tail(periods_ahead)

    # In-sample residuals
    in_sample = forecast[forecast["ds"].isin(df["ds"])].copy()
    in_sample = in_sample.set_index("ds")["yhat"]
    actual = df.set_index("ds")["y"]
    resid = (actual - in_sample).dropna()
    rmse = float((resid ** 2).mean() ** 0.5)
    mae = float(resid.abs().mean())

    result: Dict[str, Any] = {
        "series_name": series_name,
        "model_type": "Prophet",
        "n_observations": len(df),
        "forecast_horizon": periods_ahead,
        "frequency": freq,
        "in_sample_rmse": round(rmse, 4),
        "in_sample_mae": round(mae, 4),
        "forecast": fcast_tail.assign(ds=fcast_tail["ds"].dt.strftime("%Y-%m-%d"))
        .round(4)
        .to_dict(orient="records"),
    }

    text = (
        f"Prophet model fitted on '{series_name}' (n={len(df)}):\n"
        f"  In-sample RMSE={result['in_sample_rmse']}, MAE={result['in_sample_mae']}\n"
        f"  {periods_ahead}-step forecast (first 3):\n"
        + "\n".join(
            f"    {r['ds']}: {r['yhat']:.2f} [{r['yhat_lower']:.2f}, {r['yhat_upper']:.2f}]"
            for r in result["forecast"][:3]
        )
    )
    return text, result


# ---------------------------------------------------------------------------
# Forecast evaluation
# ---------------------------------------------------------------------------


@tool(response_format="content_and_artifact")
def evaluate_forecast(
    actual: List[float],
    predicted: List[float],
    series_name: str = "series",
) -> tuple[str, Dict[str, Any]]:
    """Compute MAPE, RMSE, MAE, and R² between actual and predicted values.

    Parameters
    ----------
    actual: Ground-truth values.
    predicted: Forecast / model-predicted values (same length as actual).
    series_name: Label for display purposes.
    """
    import math

    actual_s = pd.Series(actual, dtype=float)
    predicted_s = pd.Series(predicted, dtype=float)

    n = len(actual_s)
    if n != len(predicted_s):
        return (
            f"Length mismatch: actual ({n}) ≠ predicted ({len(predicted_s)}).",
            {"error": "length_mismatch"},
        )

    errors = actual_s - predicted_s
    abs_errors = errors.abs()

    rmse = float((errors ** 2).mean() ** 0.5)
    mae = float(abs_errors.mean())

    # MAPE — skip zeros in actual to avoid division by zero
    nonzero_mask = actual_s != 0
    mape = (
        float((abs_errors[nonzero_mask] / actual_s[nonzero_mask].abs()).mean()) * 100
        if nonzero_mask.any()
        else float("nan")
    )

    # R²
    ss_res = float((errors ** 2).sum())
    ss_tot = float(((actual_s - actual_s.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot != 0 else float("nan")

    # Directional accuracy (predicted direction matches actual change)
    if n > 1:
        actual_diff = actual_s.diff().dropna()
        predicted_diff = predicted_s.diff().dropna()
        da = float((np.sign(actual_diff) == np.sign(predicted_diff)).mean()) * 100
    else:
        da = float("nan")

    result: Dict[str, Any] = {
        "series_name": series_name,
        "n_observations": n,
        "rmse": round(rmse, 4),
        "mae": round(mae, 4),
        "mape_pct": round(mape, 2) if not math.isnan(mape) else None,
        "r2": round(r2, 4) if not math.isnan(r2) else None,
        "directional_accuracy_pct": round(da, 2) if not math.isnan(da) else None,
    }

    text = (
        f"Forecast evaluation for '{series_name}' (n={n}):\n"
        f"  RMSE  = {result['rmse']}\n"
        f"  MAE   = {result['mae']}\n"
        f"  MAPE  = {result['mape_pct']}%\n"
        f"  R²    = {result['r2']}\n"
        f"  Directional accuracy = {result['directional_accuracy_pct']}%"
    )
    return text, result


# ---------------------------------------------------------------------------
# AutoML forecast — races multiple algorithms, selects best by RMSE
# ---------------------------------------------------------------------------

def _season_length(freq: str) -> int:
    """Map a pandas-style frequency string to a seasonal period."""
    freq_upper = freq.upper().rstrip("S").rstrip("-")
    mapping = {
        "H": 24, "D": 7, "W": 52, "M": 12, "Q": 4,
        "A": 1, "Y": 1, "T": 60, "MIN": 60,
    }
    return mapping.get(freq_upper, 1)


def _rmse(actual: "np.ndarray", predicted: "np.ndarray") -> float:
    import numpy as _np
    err = actual - predicted
    return float(_np.sqrt(_np.mean(err ** 2)))


def _mae(actual: "np.ndarray", predicted: "np.ndarray") -> float:
    import numpy as _np
    return float(_np.mean(_np.abs(actual - predicted)))


# ---- statsforecast backend ------------------------------------------------

def _automl_statsforecast(
    values: "np.ndarray",
    freq: str,
    season_length: int,
    test_size: int,
    periods_ahead: int,
    series_name: str,
) -> Dict[str, Any]:
    """Race a comprehensive set of statistical forecasting models via statsforecast.

    Models included (15 total):
    ─ AutoML variants  : AutoARIMA, AutoETS, AutoTheta, AutoCES, AutoMFLES, AutoTBATS
    ─ Theta family     : DynamicOptimizedTheta
    ─ Exponential Sm.  : HoltWinters, Holt, SimpleExponentialSmoothing
    ─ Baselines        : SeasonalNaive, Naive, RandomWalkWithDrift,
                         HistoricAverage, WindowAverage
    """
    import numpy as _np
    import pandas as _pd
    from statsforecast import StatsForecast
    from statsforecast.models import (
        AutoARIMA,
        AutoCES,
        AutoETS,
        AutoMFLES,
        AutoTBATS,
        AutoTheta,
        DynamicOptimizedTheta,
        HistoricAverage,
        Holt,
        HoltWinters,
        Naive,
        RandomWalkWithDrift,
        SeasonalNaive,
        SimpleExponentialSmoothing,
        WindowAverage,
    )

    n = len(values)

    # Build a minimal StatsForecast DataFrame (unique_id, ds, y)
    dates = _pd.date_range(end="2020-01-01", periods=n, freq=freq)
    df_sf = _pd.DataFrame({"unique_id": series_name, "ds": dates, "y": values})

    # Build model list — skip seasonality-dependent models for season_length == 1
    sl = season_length
    models: list = [
        AutoARIMA(season_length=sl),
        AutoETS(season_length=sl),
        AutoTheta(season_length=sl),
        AutoCES(season_length=sl),
        AutoMFLES(season_length=sl),
        AutoTBATS(season_length=sl),
        DynamicOptimizedTheta(season_length=sl),
        HoltWinters(season_length=max(sl, 2)),
        Holt(),
        SimpleExponentialSmoothing(alpha=0.3),
        Naive(),
        RandomWalkWithDrift(),
        HistoricAverage(),
        WindowAverage(window_size=max(2, min(sl, n // 2))),
    ]
    if sl > 1:
        models.append(SeasonalNaive(season_length=sl))

    sf = StatsForecast(models=models, freq=freq, n_jobs=1)

    # Walk-forward cross-validation (1 window of size test_size)
    cv = sf.cross_validation(df=df_sf, h=test_size, n_windows=1)

    # Build leaderboard — drop NaN models gracefully
    model_cols = [c for c in cv.columns if c not in ("unique_id", "ds", "cutoff", "y")]
    leaderboard: list[dict] = []
    for col in model_cols:
        actual_vals = cv["y"].values
        pred_vals   = cv[col].values
        if _np.isnan(pred_vals).any():
            continue
        leaderboard.append({
            "model": col,
            "rmse":  round(_rmse(actual_vals, pred_vals), 4),
            "mae":   round(_mae(actual_vals, pred_vals), 4),
        })
    leaderboard.sort(key=lambda x: x["rmse"])
    best_model_name = leaderboard[0]["model"]

    # Refit on full series + forecast
    sf2 = StatsForecast(models=models, freq=freq, n_jobs=1)
    sf2.fit(df_sf)
    fcast = sf2.predict(h=periods_ahead)
    best_forecast = fcast[best_model_name].tolist()

    return {
        "backend": "statsforecast",
        "season_length": season_length,
        "test_size": test_size,
        "leaderboard": leaderboard,
        "best_model": best_model_name,
        "best_model_test_rmse": leaderboard[0]["rmse"],
        "best_model_test_mae": leaderboard[0]["mae"],
        "forecast": best_forecast,
        "periods_ahead": periods_ahead,
        "freq": freq,
    }


# ---- statsmodels fallback -------------------------------------------------

def _automl_statsmodels(
    values: "np.ndarray",
    season_length: int,
    test_size: int,
    periods_ahead: int,
    series_name: str,
) -> Dict[str, Any]:
    """Comprehensive AutoML fallback — runs when statsforecast is not installed.

    Models included (up to ~20 depending on optional packages):
    ─ Classic baselines    : Naive, SeasonalNaive, RandomWalkWithDrift,
                             HistoricAverage, WindowAverage
    ─ Exponential Sm.      : Holt-Winters (add/mul), Holt, SES
    ─ ARIMA grid           : SARIMAX (1,1,1), (0,1,1), (2,1,2), (1,0,1),
                             (0,1,2), (1,1,0)
    ─ TBATS (optional)     : requires ``pip install tbats``
    ─ LightGBM lag-features: requires ``pip install lightgbm``
    ─ Ridge w/ lag features: always available via scikit-learn
    """
    import math as _math
    import numpy as _np
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    n_total = len(values)
    train = values[:-test_size]
    test  = values[-test_size:]
    n_train = len(train)

    candidates: list[dict] = []

    # ---- Helper: fit statsmodels model, get test predictions ---------------
    def _try_sm(name: str, fit_fn):
        try:
            fitted = fit_fn(train)
            preds  = _np.array(fitted.forecast(test_size), dtype=float)
            if _np.isnan(preds).any():
                return {"model": name, "error": "NaN predictions"}
            return {"model": name, "fitted": fitted, "preds": preds,
                    "rmse": round(_rmse(test, preds), 4),
                    "mae":  round(_mae(test, preds), 4)}
        except Exception as exc:
            return {"model": name, "error": str(exc)}

    # ---- Helper: lag-feature matrix ----------------------------------------
    def _lag_features(series: "_np.ndarray", lags: list) -> "_np.ndarray":
        max_lag = max(lags)
        return _np.column_stack([series[max_lag - lag: len(series) - lag] for lag in lags])

    # =========================================================================
    # 1. BASELINES
    # =========================================================================
    # Naive — repeat last value
    naive_preds = _np.full(test_size, float(train[-1]))
    candidates.append({"model": "Naive", "preds": naive_preds,
                       "rmse": round(_rmse(test, naive_preds), 4),
                       "mae":  round(_mae(test, naive_preds), 4)})

    # RandomWalkWithDrift — last value + average increments
    if n_train > 1:
        drift = float(_np.mean(_np.diff(train)))
        rwd_preds = _np.array([train[-1] + drift * (i + 1) for i in range(test_size)])
        candidates.append({"model": "RandomWalkWithDrift", "preds": rwd_preds,
                           "rmse": round(_rmse(test, rwd_preds), 4),
                           "mae":  round(_mae(test, rwd_preds), 4)})

    # HistoricAverage — mean of train
    ha_preds = _np.full(test_size, float(_np.mean(train)))
    candidates.append({"model": "HistoricAverage", "preds": ha_preds,
                       "rmse": round(_rmse(test, ha_preds), 4),
                       "mae":  round(_mae(test, ha_preds), 4)})

    # WindowAverage — mean of last season window
    win = max(2, min(season_length, n_train))
    wa_preds = _np.full(test_size, float(_np.mean(train[-win:])))
    candidates.append({"model": f"WindowAverage(w={win})", "preds": wa_preds,
                       "rmse": round(_rmse(test, wa_preds), 4),
                       "mae":  round(_mae(test, wa_preds), 4)})

    # SeasonalNaive — repeat last season block
    if season_length > 1 and n_train >= season_length:
        sn_preds = _np.array([float(train[-(season_length - (i % season_length))])
                               for i in range(test_size)])
        candidates.append({"model": "SeasonalNaive", "preds": sn_preds,
                           "rmse": round(_rmse(test, sn_preds), 4),
                           "mae":  round(_mae(test, sn_preds), 4)})

    # =========================================================================
    # 2. EXPONENTIAL SMOOTHING (statsmodels)
    # =========================================================================
    if season_length > 1 and n_train >= 3 * season_length:
        for trend, seasonal in [("add", "add"), ("add", "mul"), ("add", None), (None, "add")]:
            label = f"ETS(trend={trend},seasonal={seasonal})"
            def _fit_hw(tr, t=trend, s=seasonal, sl=season_length):
                return ExponentialSmoothing(
                    tr, trend=t, seasonal=s,
                    seasonal_periods=sl if s else None,
                    damped_trend=(t == "add"),
                    initialization_method="estimated",
                ).fit(optimized=True)
            res = _try_sm(label, _fit_hw)
            if "error" not in res:
                candidates.append(res)
    else:
        for trend in ["add", None]:
            label = f"ETS(trend={trend},seasonal=None)"
            def _fit_simple(tr, t=trend):
                return ExponentialSmoothing(
                    tr, trend=t, damped_trend=(t == "add"),
                    initialization_method="estimated",
                ).fit(optimized=True)
            res = _try_sm(label, _fit_simple)
            if "error" not in res:
                candidates.append(res)

    # SES (Simple Exponential Smoothing)
    def _fit_ses(tr):
        return ExponentialSmoothing(tr, initialization_method="estimated").fit(optimized=True)
    res_ses = _try_sm("SES", _fit_ses)
    if "error" not in res_ses:
        candidates.append(res_ses)

    # =========================================================================
    # 3. ARIMA / SARIMAX (statsmodels)
    # =========================================================================
    arima_orders = [(1, 1, 1), (0, 1, 1), (2, 1, 2), (1, 0, 1), (0, 1, 2), (1, 1, 0)]
    for order in arima_orders:
        label = f"ARIMA{order}"
        s_order = (1, 1, 1, season_length) if season_length > 1 else (0, 0, 0, 0)
        def _fit_arima(tr, o=order, so=s_order):
            return SARIMAX(tr, order=o, seasonal_order=so,
                           enforce_stationarity=False,
                           enforce_invertibility=False).fit(disp=False)
        res = _try_sm(label, _fit_arima)
        if "error" not in res:
            candidates.append(res)

    # =========================================================================
    # 4. TBATS (optional — pip install tbats)
    # =========================================================================
    try:
        from tbats import TBATS as _TBATS
        tbats_estimator = _TBATS(
            seasonal_periods=[season_length] if season_length > 1 else None,
            use_arma_errors=True,
            use_trend=True,
            n_jobs=1,
            show_warnings=False,
        )
        tbats_mdl = tbats_estimator.fit(train)
        tbats_preds = _np.array(tbats_mdl.forecast(steps=test_size), dtype=float)
        if not _np.isnan(tbats_preds).any():
            candidates.append({
                "model": "TBATS",
                "preds": tbats_preds,
                "_tbats_estimator": tbats_estimator,
                "rmse": round(_rmse(test, tbats_preds), 4),
                "mae":  round(_mae(test, tbats_preds), 4),
            })
    except ImportError:
        pass
    except Exception:
        pass

    # =========================================================================
    # 5. LAG-FEATURE ML MODELS (Ridge + optional LightGBM)
    # =========================================================================
    lags = list(range(1, min(season_length + 1, n_train // 3 + 1, 14)))
    if not lags:
        lags = [1, 2]

    if n_train > max(lags) + 1:
        X_train = _lag_features(train, lags)
        y_train = train[max(lags):]

        def _recursive_predict(model, n_steps: int) -> "_np.ndarray":
            buf = list(train)
            preds_out = []
            for _ in range(n_steps):
                feat = _np.array([[buf[-l] for l in lags]])
                p = float(model.predict(feat)[0])
                preds_out.append(p)
                buf.append(p)
            return _np.array(preds_out)

        # Ridge Regression with lag features
        try:
            from sklearn.linear_model import Ridge
            ridge = Ridge(alpha=1.0)
            ridge.fit(X_train, y_train)
            ridge_preds = _recursive_predict(ridge, test_size)
            if not _np.isnan(ridge_preds).any():
                candidates.append({
                    "model": "RidgeRegression(lags)",
                    "preds": ridge_preds,
                    "_model": ridge,
                    "rmse": round(_rmse(test, ridge_preds), 4),
                    "mae":  round(_mae(test, ridge_preds), 4),
                })
        except ImportError:
            pass
        except Exception:
            pass

        # LightGBM with lag features (optional)
        try:
            import lightgbm as _lgb
            lgb_model = _lgb.LGBMRegressor(
                n_estimators=200, learning_rate=0.05,
                max_depth=5, min_child_samples=2,
                n_jobs=1, verbose=-1,
            )
            lgb_model.fit(X_train, y_train)
            lgb_preds = _recursive_predict(lgb_model, test_size)
            if not _np.isnan(lgb_preds).any():
                candidates.append({
                    "model": "LightGBM(lags)",
                    "preds": lgb_preds,
                    "_model": lgb_model,
                    "rmse": round(_rmse(test, lgb_preds), 4),
                    "mae":  round(_mae(test, lgb_preds), 4),
                })
        except ImportError:
            pass
        except Exception:
            pass

    # =========================================================================
    # Pick winner & refit on full series
    # =========================================================================
    valid = [c for c in candidates if "rmse" in c and not _math.isnan(c["rmse"])]
    if not valid:
        naive_preds = _np.full(test_size, float(values[-1]))
        valid = [{"model": "Naive", "preds": naive_preds,
                  "rmse": round(_rmse(test, naive_preds), 4),
                  "mae":  round(_mae(test, naive_preds), 4)}]
    valid.sort(key=lambda x: x["rmse"])
    best_name = valid[0]["model"]

    # Refit best model on full series
    try:
        if best_name == "Naive":
            best_forecast = [float(values[-1])] * periods_ahead
        elif best_name == "RandomWalkWithDrift":
            d = float(_np.mean(_np.diff(values)))
            best_forecast = [float(values[-1]) + d * (i + 1) for i in range(periods_ahead)]
        elif best_name == "HistoricAverage":
            best_forecast = [float(_np.mean(values))] * periods_ahead
        elif best_name.startswith("WindowAverage"):
            best_forecast = [float(_np.mean(values[-win:]))] * periods_ahead
        elif best_name == "SeasonalNaive":
            best_forecast = [float(values[-(season_length - (i % season_length))])
                             for i in range(periods_ahead)]
        elif best_name.startswith("ETS"):
            params: dict = {}
            if "trend=add" in best_name:    params["trend"] = "add"; params["damped_trend"] = True
            if "seasonal=add" in best_name: params["seasonal"] = "add"; params["seasonal_periods"] = season_length
            if "seasonal=mul" in best_name: params["seasonal"] = "mul"; params["seasonal_periods"] = season_length
            ets_full = ExponentialSmoothing(
                values, initialization_method="estimated", **params
            ).fit(optimized=True)
            best_forecast = ets_full.forecast(periods_ahead).tolist()
        elif best_name == "SES":
            ses_full = ExponentialSmoothing(
                values, initialization_method="estimated"
            ).fit(optimized=True)
            best_forecast = ses_full.forecast(periods_ahead).tolist()
        elif best_name.startswith("ARIMA"):
            import ast
            order = ast.literal_eval(best_name.replace("ARIMA", ""))
            s_order = (1, 1, 1, season_length) if season_length > 1 else (0, 0, 0, 0)
            full_fit = SARIMAX(values, order=order, seasonal_order=s_order,
                               enforce_stationarity=False,
                               enforce_invertibility=False).fit(disp=False)
            best_forecast = full_fit.forecast(periods_ahead).tolist()
        elif best_name == "TBATS":
            tbats_full = valid[0]["_tbats_estimator"].fit(values)
            best_forecast = list(_np.array(tbats_full.forecast(steps=periods_ahead), dtype=float))
        elif best_name in ("RidgeRegression(lags)", "LightGBM(lags)"):
            ml_model = valid[0]["_model"]

            def _rec_pred_full(mdl, n_steps):
                buf = list(values)
                out = []
                for _ in range(n_steps):
                    feat = _np.array([[buf[-l] for l in lags]])
                    p = float(mdl.predict(feat)[0])
                    out.append(p)
                    buf.append(p)
                return out

            best_forecast = _rec_pred_full(ml_model, periods_ahead)
        else:
            best_forecast = []
    except Exception:
        best_forecast = []

    leaderboard = [{"model": c["model"], "rmse": c["rmse"], "mae": c["mae"]}
                   for c in valid]

    return {
        "backend": "statsmodels",
        "season_length": season_length,
        "test_size": test_size,
        "leaderboard": leaderboard,
        "best_model": best_name,
        "best_model_test_rmse": valid[0]["rmse"],
        "best_model_test_mae": valid[0]["mae"],
        "forecast": best_forecast,
        "periods_ahead": periods_ahead,
    }


@tool(response_format="content_and_artifact")
def auto_forecast(
    data: List[float],
    periods_ahead: int = 12,
    freq: str = "M",
    series_name: str = "series",
    test_size: Optional[int] = None,
    backend: str = "auto",
) -> tuple[str, Dict[str, Any]]:
    """AutoML time-series forecasting: races multiple algorithms and selects
    the best one by walk-forward RMSE on a holdout set.

    Parameters
    ----------
    data         : List of numeric values in chronological order.
    periods_ahead: How many future steps to forecast with the winning model.
    freq         : Pandas frequency string — 'M' (monthly), 'W' (weekly),
                   'D' (daily), 'Q' (quarterly), 'H' (hourly), 'Y' (yearly).
    series_name  : Label for display / artefact key.
    test_size    : Size of holdout set for model comparison (default: max of
                   10% of series length and 2× the seasonal period).
    backend      : 'auto' (try statsforecast first, fall back to statsmodels),
                   'statsforecast', or 'statsmodels'.

    Returns a textual leaderboard + dict with keys:
        backend, season_length, test_size, leaderboard (sorted by RMSE),
        best_model, best_model_test_rmse, best_model_test_mae,
        forecast (list of floats), periods_ahead, freq.

    Install options
    ---------------
    Fast (recommended): pip install statsforecast
    Fallback built-in:  pip install statsmodels  (already required by other tools)
    """

    try:
        import numpy as _np
    except ImportError:
        raise ImportError("pip install numpy")

    values = _np.array(data, dtype=float)
    n = len(values)
    if n < 10:
        err = {"error": "Series too short for AutoML (need ≥ 10 observations).", "n": n}
        return "AutoML failed: series too short.", err

    sl = _season_length(freq)
    if test_size is None:
        test_size = max(int(n * 0.1), 2 * sl, 2)
    if test_size >= n:
        test_size = max(2, n // 5)

    # ---- Choose backend ---------------------------------------------------
    use_sf = False
    if backend in ("auto", "statsforecast"):
        try:
            import statsforecast  # noqa: F401
            use_sf = True
        except ImportError:
            if backend == "statsforecast":
                raise ImportError(
                    "statsforecast not found. Install: pip install statsforecast"
                )

    if use_sf:
        try:
            result = _automl_statsforecast(values, freq, sl, test_size, periods_ahead, series_name)
        except Exception as exc:
            return f"AutoML (statsforecast) failed: {exc}", {"error": str(exc), "series_name": series_name}
    else:
        try:
            from statsmodels.tsa.holtwinters import ExponentialSmoothing  # noqa: F401
        except ImportError:
            raise ImportError("pip install statsmodels")
        try:
            result = _automl_statsmodels(values, sl, test_size, periods_ahead, series_name)
        except Exception as exc:
            return f"AutoML (statsmodels) failed: {exc}", {"error": str(exc), "series_name": series_name}

    result["series_name"] = series_name

    # Build leaderboard text
    lb_lines = "\n".join(
        f"  {i+1}. {r['model']:35s} RMSE={r['rmse']:.4f}  MAE={r['mae']:.4f}"
        for i, r in enumerate(result["leaderboard"])
    )
    text = (
        f"AutoML Forecasting — '{series_name}' (n={n}, freq={freq}, "
        f"backend={result['backend']})\n"
        f"Holdout size: {test_size}\n\n"
        f"Leaderboard (ranked by holdout RMSE):\n{lb_lines}\n\n"
        f"Winner: {result['best_model']}\n"
        f"  Test RMSE = {result['best_model_test_rmse']}\n"
        f"  Test MAE  = {result['best_model_test_mae']}\n"
        f"  {periods_ahead}-step forecast: "
        f"{[round(v, 4) for v in result['forecast'][:6]]}{'...' if periods_ahead > 6 else ''}"
    )
    return text, result
