"""GERÇEK test balance_agent tool doğrulaması (PM kararı: skip yok).

Kapsam: ai_data_science_team/agents/balance_agent.py — 9 tool.

Strateji:
- PURE (model-driven): ``class_distribution_wrapped``,
  ``undersample_indices_wrapped``, ``class_weight_wrapped``,
  ``apply_strategy_wrapped`` model tarafından çağrılır.
- STATEFUL: ``is_imbalanced``, ``select_strategy``, ``estimate_strategy_impact``,
  ``recommend_metrics``, ``balance_payload`` için gerçek ``ClassDistribution``
  dataclass yaratılır ve **underlying tool** doğrudan çağrılır.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.balance_agent import (
    apply_strategy_wrapped,
    class_distribution_wrapped,
    class_weight_wrapped,
    undersample_indices_wrapped,
)
from ai_data_science_team.tools.balance import (
    ClassDistribution,
    balance_payload,
    estimate_strategy_impact,
    is_imbalanced,
    recommend_metrics,
    select_strategy,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# 1. PURE: yalnızca skaler/str argümanlar, model-driven
# ---------------------------------------------------------------------------

def test_class_distribution_real(llm_or_skip, llm_model):
    tool = class_distribution_wrapped
    _content, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "class_distribution_wrapped tool'unu TEK çağrı ile çağır; y=['a','a','b'] ver.",
        ),
        tool.name,
    )


def test_undersample_indices_real(llm_or_skip, llm_model):
    tool = undersample_indices_wrapped
    _content, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "undersample_indices_wrapped tool'unu TEK çağrı ile çağır; "
            "y=['a','a','b','b'] ver.",
        ),
        tool.name,
    )


def test_class_weight_real(llm_or_skip, llm_model):
    tool = class_weight_wrapped
    _content, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "class_weight_wrapped tool'unu TEK çağrı ile çağır; y=['a','a','b'] ver.",
        ),
        tool.name,
    )


def test_apply_strategy_real(llm_or_skip, llm_model):
    tool = apply_strategy_wrapped
    _content, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "apply_strategy_wrapped tool'unu TEK çağrı ile çağır; "
            "y=['a','a','b'], strategy='class_weight' ver.",
        ),
        tool.name,
    )


# ---------------------------------------------------------------------------
# 2. STATEFUL: ClassDistribution gerektiren tool'lar
# ---------------------------------------------------------------------------

def _imbalanced_dist() -> ClassDistribution:
    """Orta seviye dengesizlik: 8 'a', 2 'b' → IR=4.0."""
    return ClassDistribution(
        counts={"a": 8, "b": 2},
        n=10,
        n_classes=2,
        majority_count=8,
        minority_count=2,
        imbalance_ratio=4.0,
    )


def _balanced_dist() -> ClassDistribution:
    return ClassDistribution(
        counts={"a": 5, "b": 5},
        n=10,
        n_classes=2,
        majority_count=5,
        minority_count=5,
        imbalance_ratio=1.0,
    )


def test_is_imbalanced_real():
    """is_imbalanced: severity + threshold raporu."""
    out = is_imbalanced(_imbalanced_dist())
    assert out["is_imbalanced"] is True
    assert out["severity"] == "moderate"
    out_bal = is_imbalanced(_balanced_dist())
    assert out_bal["is_imbalanced"] is False
    assert out_bal["severity"] == "balanced"


def test_select_strategy_real():
    """select_strategy: heuristic primary + rationale."""
    out = select_strategy(_imbalanced_dist())
    assert out["primary"] in {"class_weight", "threshold_tuning", "smote", "undersampling"}
    assert "rationale" in out
    out_bal = select_strategy(_balanced_dist())
    assert out_bal["primary"] == "none"


def test_estimate_strategy_impact_real():
    """estimate_strategy_impact: before/after n + imbalance_ratio."""
    out = estimate_strategy_impact(_imbalanced_dist(), strategy="class_weight")
    assert out["strategy"] == "class_weight"
    assert out["before"]["n"] == 10
    assert out["before"]["imbalance_ratio"] == 4.0
    # class_weight no resampling
    assert out["after"]["n"] == 10
    out_sm = estimate_strategy_impact(_imbalanced_dist(), strategy="smote")
    assert out_sm["after"]["n"] >= 10
    assert out_sm["effective"] is True


def test_recommend_metrics_real():
    """recommend_metrics: imbalanced → pr_auc, balanced → accuracy."""
    rec = recommend_metrics(_imbalanced_dist())
    assert rec.primary_metric == "pr_auc"
    rec_bal = recommend_metrics(_balanced_dist())
    assert rec_bal.primary_metric == "accuracy"


def test_balance_payload_real():
    """balance_payload: dashboard-ready {distribution, verdict, ...} dict."""
    payload = balance_payload(_imbalanced_dist())
    assert payload["distribution"]["n"] == 10
    assert payload["distribution"]["imbalance_ratio"] == 4.0
    assert payload["selected_strategy"] in {
        "class_weight",
        "threshold_tuning",
        "smote",
        "undersampling",
    }
    assert payload["recommended_metrics"]["primary"] == "pr_auc"
    assert "rationale" in payload
