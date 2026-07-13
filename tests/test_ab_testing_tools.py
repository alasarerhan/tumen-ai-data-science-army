"""
Unit tests for ``ai_data_science_team.tools.ab_testing``.

These tests exercise the deterministic statistical core of the A1
AB Testing Agent (spec from ``docs/AGENT_SPEC_CATALOG.md``) without
requiring an LLM or the LangGraph runtime.

Run with:
    pytest tests/test_ab_testing_tools.py -v
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ai_data_science_team.tools.ab_testing import (
    analyze_continuous_metric,
    analyze_proportion_metric,
    apply_cuped,
    apply_multiple_comparison_correction,
    check_sample_ratio_mismatch,
    detect_sequential_peeking,
    recommend_decision,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def continuous_experiment() -> pd.DataFrame:
    """Continuous metric experiment with a real +5% lift."""
    rng = np.random.default_rng(42)
    n_per_arm = 5000
    control = rng.normal(loc=10.0, scale=2.0, size=n_per_arm)
    treatment = rng.normal(loc=10.5, scale=2.0, size=n_per_arm)
    return pd.DataFrame(
        {
            "user_id": range(2 * n_per_arm),
            "group": ["control"] * n_per_arm + ["treatment"] * n_per_arm,
            "revenue": np.concatenate([control, treatment]),
        }
    )


@pytest.fixture
def proportion_experiment() -> pd.DataFrame:
    """Binary conversion metric with a real +1pp absolute lift."""
    rng = np.random.default_rng(7)
    n_per_arm = 4000
    control_conv = rng.binomial(1, 0.10, size=n_per_arm)
    treatment_conv = rng.binomial(1, 0.11, size=n_per_arm)
    return pd.DataFrame(
        {
            "user_id": range(2 * n_per_arm),
            "group": ["control"] * n_per_arm + ["treatment"] * n_per_arm,
            "converted": np.concatenate([control_conv, treatment_conv]),
        }
    )


@pytest.fixture
def srm_skewed_experiment() -> pd.DataFrame:
    """60/40 split but the observed counts are 55/45 — should NOT trigger SRM."""
    rng = np.random.default_rng(1)
    n_control, n_treatment = 5500, 4500
    return pd.DataFrame(
        {
            "user_id": range(n_control + n_treatment),
            "group": ["control"] * n_control + ["treatment"] * n_treatment,
            "metric": rng.normal(0, 1, n_control + n_treatment),
        }
    )


# ---------------------------------------------------------------------------
# 1. Sample Ratio Mismatch
# ---------------------------------------------------------------------------


def test_srm_passes_with_balanced_split(continuous_experiment) -> None:
    result = check_sample_ratio_mismatch(
        continuous_experiment, group_column="group"
    )
    assert result["srm_detected"] is False
    assert result["n_per_group"]["control"] == 5000
    assert result["n_per_group"]["treatment"] == 5000
    assert result["p_value"] > 0.05


def test_srm_detects_skewed_split() -> None:
    rng = np.random.default_rng(2)
    # Expected 50/50 but observed 50/40 → strong SRM signal.
    df = pd.DataFrame(
        {
            "user_id": range(9000),
            "group": ["control"] * 5000 + ["treatment"] * 4000,
            "x": rng.normal(size=9000),
        }
    )
    result = check_sample_ratio_mismatch(df, group_column="group")
    assert result["srm_detected"] is True
    assert result["p_value"] < 0.001
    assert "deviate" in result["warning"]


def test_srm_respects_expected_split() -> None:
    rng = np.random.default_rng(3)
    df = pd.DataFrame(
        {
            "group": ["A"] * 1000 + ["B"] * 1000 + ["C"] * 1000,
            "x": rng.normal(size=3000),
        }
    )
    result = check_sample_ratio_mismatch(
        df, group_column="group", expected_split={"A": 1 / 3, "B": 1 / 3, "C": 1 / 3}
    )
    assert result["srm_detected"] is False
    assert set(result["n_per_group"].keys()) == {"A", "B", "C"}


# ---------------------------------------------------------------------------
# 2. Continuous metric analysis
# ---------------------------------------------------------------------------


def test_continuous_detects_real_lift(continuous_experiment) -> None:
    result = analyze_continuous_metric(
        continuous_experiment,
        group_column="group",
        metric_column="revenue",
        control_name="control",
    )
    assert result["test_used"] in {"welch_t", "mann_whitney_u"}
    assert result["p_value"] < 0.01  # real +5% lift should be detected
    assert result["control_mean"] < result["treatment_mean"]
    assert result["ci_low"] < result["ci_high"]
    assert result["ci_low"] < result["absolute_lift"] < result["ci_high"]
    assert result["effect_size"] > 0


def test_continuous_returns_null_effect_for_identical_groups() -> None:
    rng = np.random.default_rng(0)
    n = 500
    df = pd.DataFrame(
        {
            "group": ["control"] * n + ["treatment"] * n,
            "x": np.concatenate(
                [rng.normal(5, 1, n), rng.normal(5, 1, n)]
            ),
        }
    )
    result = analyze_continuous_metric(df, "group", "x")
    assert result["p_value"] > 0.05
    assert abs(result["absolute_lift"]) < 0.2  # within sampling noise


def test_continuous_uses_nonparametric_for_skewed() -> None:
    rng = np.random.default_rng(99)
    n = 600
    # Log-normal / exponential = clearly non-normal.
    df = pd.DataFrame(
        {
            "group": ["control"] * n + ["treatment"] * n,
            "x": np.concatenate(
                [rng.exponential(1.0, n), rng.exponential(1.2, n)]
            ),
        }
    )
    result = analyze_continuous_metric(df, "group", "x")
    # Shapiro / normaltest should reject normality → fallback to MWU.
    assert result["test_used"] == "mann_whitney_u"
    assert result["p_value"] < 0.05


# ---------------------------------------------------------------------------
# 3. Proportion metric analysis
# ---------------------------------------------------------------------------


def test_proportion_detects_real_lift(proportion_experiment) -> None:
    result = analyze_proportion_metric(
        proportion_experiment,
        group_column="group",
        metric_column="converted",
        control_name="control",
    )
    assert result["metric_type"] == "proportion"
    assert result["p_value"] < 0.05
    assert result["treatment_mean"] > result["control_mean"]
    assert result["ci_low"] < result["ci_high"]
    assert result["treatment_ci"][0] < result["treatment_ci"][1]


def test_proportion_handles_no_lift() -> None:
    rng = np.random.default_rng(11)
    n = 3000
    df = pd.DataFrame(
        {
            "group": ["control"] * n + ["treatment"] * n,
            "converted": np.concatenate(
                [
                    rng.binomial(1, 0.10, n),
                    rng.binomial(1, 0.10, n),
                ]
            ),
        }
    )
    result = analyze_proportion_metric(df, "group", "converted")
    assert result["p_value"] > 0.05


# ---------------------------------------------------------------------------
# 4. CUPED variance reduction
# ---------------------------------------------------------------------------


def test_cuped_reduces_variance_when_covariate_correlates() -> None:
    rng = np.random.default_rng(5)
    n = 2000
    covariate = rng.normal(0, 1, n)
    noise = rng.normal(0, 1, n)
    metric_control = 2.0 * covariate + noise
    metric_treatment = 2.0 * covariate + noise + 0.5  # true lift = 0.5
    df = pd.DataFrame(
        {
            "group": ["control"] * n + ["treatment"] * n,
            "metric": np.concatenate([metric_control, metric_treatment]),
            "pre": np.concatenate([covariate, covariate]),
        }
    )
    result = apply_cuped(
        df, group_column="group", metric_column="metric", covariate_column="pre"
    )
    assert result["variance_reduction_pct"] > 30.0
    # Adjusted lift should be close to the true lift of 0.5.
    assert abs(result["absolute_lift_adjusted"] - 0.5) < 0.1


def test_cuped_handles_uncorrelated_covariate() -> None:
    rng = np.random.default_rng(6)
    n = 1500
    df = pd.DataFrame(
        {
            "group": ["control"] * n + ["treatment"] * n,
            "metric": np.concatenate([rng.normal(0, 1, n), rng.normal(0.3, 1, n)]),
            "pre": rng.normal(0, 1, 2 * n),
        }
    )
    result = apply_cuped(df, "group", "metric", "pre")
    # Uncorrelated covariate → near-zero variance reduction.
    assert result["variance_reduction_pct"] < 5.0


# ---------------------------------------------------------------------------
# 5. Multiple comparison correction
# ---------------------------------------------------------------------------


def test_bonferroni_correction_is_conservative() -> None:
    p_values = [0.01, 0.04, 0.03, 0.5]
    result = apply_multiple_comparison_correction(p_values, method="bonferroni")
    assert result["method"] == "bonferroni"
    assert all(adj >= raw for adj, raw in zip(result["adjusted"], p_values))
    # Original 0.01 stays significant; 0.04 → 0.16 (not significant).
    assert result["adjusted"][0] < 0.05
    assert result["adjusted"][1] >= 0.05


def test_bh_correction_preserves_ordering() -> None:
    p_values = [0.001, 0.01, 0.04, 0.5]
    result = apply_multiple_comparison_correction(p_values, method="bh")
    assert result["method"] == "bh"
    # Adjusted p-values must be non-decreasing when ranked ascending.
    order = np.argsort(p_values)
    adj_sorted = np.array(result["adjusted"])[order]
    assert all(adj_sorted[i] <= adj_sorted[i + 1] + 1e-9 for i in range(len(adj_sorted) - 1))
    # BH should reject the first two at alpha=0.05.
    assert result["rejected"][0] is True


def test_no_correction_passthrough() -> None:
    p_values = [0.01, 0.04]
    result = apply_multiple_comparison_correction(p_values, method="none")
    assert result["adjusted"] == p_values


# ---------------------------------------------------------------------------
# 6. Sequential testing peeking
# ---------------------------------------------------------------------------


def test_peeking_warns_when_interim_crossed_alpha_below_avt() -> None:
    # 5 looks; min p=0.04 is naively significant (0.04 < 0.05) but NOT
    # Bonferroni-robust (0.04 > 0.05/5 = 0.01). Classic peeking risk.
    sequential = [0.20, 0.10, 0.07, 0.04, 0.06]
    result = detect_sequential_peeking(sequential, alpha=0.05)
    assert result["n_looks"] == 5
    assert result["naive_significant"] is True
    assert result["bonferroni_significant"] is False
    assert "Peeking risk" in result["peeking_warning"]


def test_peeking_ok_when_below_alpha() -> None:
    sequential = [0.5, 0.4, 0.3, 0.2]
    result = detect_sequential_peeking(sequential, alpha=0.05)
    assert result["naive_significant"] is False
    assert result["bonferroni_significant"] is False
    assert "No interim look" in result["peeking_warning"]


def test_peeking_handles_empty_input() -> None:
    result = detect_sequential_peeking([], alpha=0.05)
    assert result["n_looks"] == 0
    assert result["min_p_value"] is None
    assert "no sequential" in result["peeking_warning"]


# ---------------------------------------------------------------------------
# 7. Decision recommendation
# ---------------------------------------------------------------------------


def test_recommend_decision_ship_when_significant_and_mde_met() -> None:
    metric_result = {
        "metric": "revenue",
        "p_value": 0.001,
        "relative_lift": 0.05,
        "alpha": 0.05,
    }
    decision = recommend_decision(
        metric_result, min_detectable_lift=0.02, required_sample_ratio=1.0
    )
    assert decision["decision"] == "ship"
    assert "Significant" in decision["rationale"]
    assert decision["mde_met"] is True


def test_recommend_decision_iterate_when_lift_below_mde() -> None:
    metric_result = {
        "metric": "revenue",
        "p_value": 0.01,
        "relative_lift": 0.005,
        "alpha": 0.05,
    }
    decision = recommend_decision(
        metric_result, min_detectable_lift=0.02, required_sample_ratio=1.0
    )
    assert decision["decision"] == "iterate"
    assert decision["mde_met"] is False


def test_recommend_decision_abort_when_not_significant() -> None:
    metric_result = {
        "metric": "revenue",
        "p_value": 0.42,
        "relative_lift": -0.005,
        "alpha": 0.05,
    }
    decision = recommend_decision(
        metric_result, min_detectable_lift=0.02, required_sample_ratio=1.0
    )
    assert decision["decision"] == "abort"


def test_recommend_decision_watch_when_underpowered() -> None:
    metric_result = {
        "metric": "revenue",
        "p_value": 0.20,
        "relative_lift": 0.01,
        "alpha": 0.05,
    }
    decision = recommend_decision(
        metric_result, min_detectable_lift=0.02, required_sample_ratio=0.5
    )
    assert decision["decision"] == "watch"
    assert decision["underpowered"] is True


def test_recommend_decision_ship_without_mde_when_significant() -> None:
    """When no MDE is provided, any significant effect yields 'ship'."""
    metric_result = {
        "metric": "revenue",
        "p_value": 0.001,
        "relative_lift": 0.01,
        "alpha": 0.05,
    }
    decision = recommend_decision(metric_result, min_detectable_lift=None)
    assert decision["decision"] == "ship"
    assert decision["mde_met"] is None


# ---------------------------------------------------------------------------
# 8. Agent-class wiring (no-LLM smoke test)
# ---------------------------------------------------------------------------


def test_agent_module_exports() -> None:
    """The agent module must expose the public API the catalog expects."""
    from ai_data_science_team.agents.ab_testing_agent import (  # noqa: F401
        AGENT_NAME,
        NODE_TYPE,
        ABTestingAgent,
        make_ab_testing_agent,
        AB_TESTING_TOOLS,
    )
    assert AGENT_NAME == "ab_testing_agent"
    assert NODE_TYPE == "experiment.analyze"
    assert {t.name for t in AB_TESTING_TOOLS} >= {
        "ab_check_srm",
        "ab_analyze_continuous",
        "ab_analyze_proportion",
        "ab_apply_cuped",
        "ab_correct_multiple",
        "ab_detect_peeking",
        "ab_recommend_decision",
    }


def test_agent_class_instantiation_without_model() -> None:
    """``ABTestingAgent`` requires an LLM only at ``make_*`` time, not in __init__."""
    from ai_data_science_team.agents.ab_testing_agent import ABTestingAgent

    # Passing model=None to __init__ is allowed because the graph is built
    # lazily; graph compilation only happens in ``make_ab_testing_agent``,
    # which DOES require a real model.  We therefore assert only that the
    # object can be created and its params are stored.
    agent = ABTestingAgent(model=None)  # type: ignore[arg-type]
    assert agent._params["alpha"] == 0.05
    assert agent._params["group_column"] == "group"
    assert agent.response is None


# ---------------------------------------------------------------------------
# 9. End-to-end orchestrator: chaining tools as the LLM would
# ---------------------------------------------------------------------------


def test_end_to_end_pipeline_on_synthetic_dataset() -> None:
    """Simulate what the LLM-driven agent would do: SRM → analyze → CUPED →
    multiple-comparison correction → decision."""
    rng = np.random.default_rng(2024)
    n = 3000
    covariate = rng.normal(0, 1, 2 * n)
    noise = rng.normal(0, 1, 2 * n)
    # Two metrics: revenue (continuous, +5% lift) and conversion (proportion, ~0).
    df = pd.DataFrame(
        {
            "user_id": range(2 * n),
            "group": ["control"] * n + ["treatment"] * n,
            "revenue": np.concatenate(
                [10 + 2 * covariate[:n] + noise[:n],
                 10.5 + 2 * covariate[n:] + noise[n:]]
            ),
            "pre_revenue": np.concatenate([covariate[:n], covariate[n:]]),
            "converted": rng.binomial(1, 0.10, 2 * n),
        }
    )

    srm = check_sample_ratio_mismatch(df, "group")
    assert srm["srm_detected"] is False

    rev = analyze_continuous_metric(df, "group", "revenue")
    conv = analyze_proportion_metric(df, "group", "converted")

    cuped = apply_cuped(df, "group", "revenue", "pre_revenue")
    assert cuped["variance_reduction_pct"] > 0

    mcc = apply_multiple_comparison_correction(
        [rev["p_value"], conv["p_value"]], method="bh"
    )
    assert len(mcc["adjusted"]) == 2

    decision = recommend_decision(
        rev, min_detectable_lift=0.02, required_sample_ratio=1.0
    )
    # +5% lift at n=3000/arm should ship confidently.
    assert decision["decision"] == "ship"
