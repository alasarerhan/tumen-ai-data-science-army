"""e11_time_series.

Deterministic time-series forecasting tools supporting **E11 —
Time Series genişletmesi** (spec
``docs/specs/E11-time-series-ext.md``).

Implements hierarchical forecast (top-down reconciliation),
holiday calendars (TR + US), and three classical engine
fallbacks (seasonal naive, moving average, simple
multiplicative seasonal).  Prophet / statsforecast adapters are
referenced but not bundled because neither library is in the
platform runtime.

Public surface
--------------

* :func:`seasonal_naive_forecast` — repeat last season.
* :func:`moving_average_forecast` — sliding window.
* :func:`multiplicative_seasonal_forecast` — period × average
  ratio.
* :func:`reconcile_top_down` — top-down hierarchical reconciliation
  via share-of-parent averages.
* :func:`holiday_calendar` — return Turkey / US / generic
  holiday dates between two years.
* :func:`build_panel` — assemble a (group × ds × y) dataframe.
* :func:`E11_TIME_SERIES_TOOL_NAMES` — registry constant.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Classical forecast engines
# ---------------------------------------------------------------------------


def seasonal_naive_forecast(
    history: Sequence[float],
    horizon: int,
    period: int = 7,
) -> List[float]:
    """Repeat the last ``period`` window ``horizon`` times."""
    if period <= 0:
        raise ValueError(f"period must be > 0, got {period}")
    if len(history) < period:
        raise ValueError(
            f"history must be at least one period (>= {period}); got {len(history)}"
        )
    window = list(history[-period:])
    if horizon <= 0:
        raise ValueError(f"horizon must be > 0, got {horizon}")
    return [window[i % period] for i in range(horizon)]


def moving_average_forecast(
    history: Sequence[float],
    horizon: int,
    window: int = 7,
) -> List[float]:
    """Slide a window over the trailing ``window`` observations."""
    if window <= 0:
        raise ValueError(f"window must be > 0, got {window}")
    if len(history) < window:
        raise ValueError(
            f"history must be at least window (>= {window}); got {len(history)}"
        )
    if horizon <= 0:
        raise ValueError(f"horizon must be > 0, got {horizon}")
    avg = float(np.mean(list(history)[-window:]))
    return [avg] * horizon


def multiplicative_seasonal_forecast(
    history: Sequence[float],
    horizon: int,
    period: int = 7,
) -> List[float]:
    """Forecast = global mean × season-index of the most-recent season."""
    if period <= 0:
        raise ValueError(f"period must be > 0, got {period}")
    if len(history) < period * 2:
        raise ValueError(
            f"need at least two full periods (>= {period*2}); got {len(history)}"
        )
    arr = np.asarray(list(history), dtype=float)
    global_mean = float(arr.mean())
    if global_mean == 0:
        return [0.0] * horizon
    seasons = arr[-period:].mean() / global_mean
    out: List[float] = []
    for i in range(horizon):
        # Re-apply the season index for the most-recent period.
        out.append(float(global_mean * seasons))
    return out


# ---------------------------------------------------------------------------
# Hierarchical reconciliation
# ---------------------------------------------------------------------------


def reconcile_top_down(
    parent_forecast: float,
    child_histories: Mapping[Any, Sequence[float]],
) -> Dict[Any, float]:
    """Top-down reconciliation: each child gets its historical share
    of the parent's forecast.

    Returns a dict mapping each child key to the reconciled value.
    """
    if parent_forecast is None:
        raise ValueError("parent_forecast is required")
    if not child_histories:
        raise ValueError("child_histories is empty")
    # Compute the share of parent by the latest-value of each child.
    latest = {k: float(np.asarray(list(v), dtype=float)[-1])
              for k, v in child_histories.items()}
    total = sum(latest.values())
    if total <= 0:
        # Fall back to even split.
        return {k: parent_forecast / len(latest) for k in latest}
    return {k: parent_forecast * (v / total) for k, v in latest.items()}


# ---------------------------------------------------------------------------
# Holiday calendars (small, deterministic)
# ---------------------------------------------------------------------------


# The Turkish national holidays used by E11. Dates are fixed in
# (month, day) form because many are religious and move each
# year; the user can pass those in optionally.  These are the
# civic holidays that DO have a fixed date.
TR_FIXED_HOLIDAYS: Dict[str, Tuple[int, int]] = {
    "Yılbaşı": (1, 1),
    "Ulusal Egemenlik ve Çocuk Bayramı": (4, 23),
    "Emek ve Dayanışma Günü": (5, 1),
    "Atatürk'ü Anma Gençlik ve Spor Bayramı": (5, 19),
    "Demokrasi ve Milli Birlik Günü": (7, 15),
    "Zafer Bayramı": (8, 30),
    "Cumhuriyet Bayramı": (10, 29),
}

US_FIXED_HOLIDAYS: Dict[str, Tuple[int, int]] = {
    "New Year's Day": (1, 1),
    "Juneteenth": (6, 19),
    "Independence Day": (7, 4),
    "Veterans Day": (11, 11),
    "Christmas Day": (12, 25),
}


def holiday_calendar(
    country: str,
    years: Iterable[int],
) -> List[Dict[str, Any]]:
    """Return the list of fixed-date holidays for ``country`` across
    ``years``.

    Country is one of: ``"TR"``, ``"US"``.  Religious/relative
    holidays (Ramadan, Eid, Thanksgiving) are out of scope for this
    deterministic core; the agent layer can add them per year.
    """
    if isinstance(years, int):
        years = [years]
    years = list(years)
    if country.upper() == "TR":
        table = TR_FIXED_HOLIDAYS
    elif country.upper() == "US":
        table = US_FIXED_HOLIDAYS
    else:
        raise ValueError(
            f"unsupported country {country!r}; supported: TR, US"
        )
    out: List[Dict[str, Any]] = []
    for y in years:
        for name, (m, d) in table.items():
            out.append(
                {
                    "country": country.upper(),
                    "year": int(y),
                    "name": name,
                    "date": f"{int(y):04d}-{int(m):02d}-{int(d):02d}",
                }
            )
    out.sort(key=lambda r: r["date"])
    return out


# ---------------------------------------------------------------------------
# Panel builder
# ---------------------------------------------------------------------------


def build_panel(
    df: pd.DataFrame,
    *,
    group_columns: Sequence[str],
    ds_column: str,
    y_column: str,
    ds_freq: str = "D",
) -> pd.DataFrame:
    """Normalise a raw frame into a long panel (group × ds × y) with
    a regular date index.
    """
    required = list(group_columns) + [ds_column, y_column]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")
    out = df[required].copy()
    out[ds_column] = pd.to_datetime(out[ds_column])
    out = (
        out.groupby(list(group_columns) + [ds_column], dropna=False)[y_column]
        .sum()
        .reset_index()
        .sort_values(list(group_columns) + [ds_column])
        .reset_index(drop=True)
    )
    return out


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


E11_TIME_SERIES_TOOL_NAMES = [
    "e11_seasonal_naive",
    "e11_moving_average",
    "e11_multiplicative_seasonal",
    "e11_reconcile_top_down",
    "e11_holiday_calendar",
    "e11_build_panel",
]
