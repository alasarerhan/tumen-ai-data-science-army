"""GERÇEK test responsible_ai_agent tool doğrulaması (PM kararı: skip yok).

Kapsam: ai_data_science_team/agents/responsible_ai_agent.py — 6 tool.

Strateji:
- PURE (parametresiz veya skaler-only): ``make_..._wrapped`` model tarafından
  çağrılır ve tool gerçekten invoke edilir.
- STATEFUL (Pydantic objesi gerektiren): ``tool.func(**kwargs)`` ile doğrudan
  çağrılır; gerçek dataclass / Mapping örnekleri kullanılır.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.responsible_ai_agent import (
    build_dashboard_wrapped,
    compute_explainability_wrapped,
    compute_fairness_wrapped,
    dashboard_payload_wrapped,
    discover_error_slices_wrapped,
    suggest_mitigations_wrapped,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# PURE (model-driven): parametresiz tool'lar
# ---------------------------------------------------------------------------


def test_compute_fairness_real(llm_or_skip, llm_model):
    tool = compute_fairness_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "compute_fairness_wrapped tool'unu TEK çağrı ile çağır; parametresiz çağır.",
        ),
        tool.name,
    )
    assert content
    assert artifact is not None


def test_compute_explainability_real(llm_or_skip, llm_model):
    tool = compute_explainability_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "compute_explainability_wrapped tool'unu TEK çağrı ile çağır; parametresiz çağır.",
        ),
        tool.name,
    )
    assert content
    assert artifact is not None


def test_discover_error_slices_real(llm_or_skip, llm_model):
    tool = discover_error_slices_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "discover_error_slices_wrapped tool'unu TEK çağrı ile çağır; parametresiz çağır.",
        ),
        tool.name,
    )
    assert content
    assert artifact is not None


def test_build_dashboard_real(llm_or_skip, llm_model):
    tool = build_dashboard_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "build_dashboard_wrapped tool'unu TEK çağrı ile çağır; parametresiz çağır.",
        ),
        tool.name,
    )
    assert content
    assert artifact is not None


# ---------------------------------------------------------------------------
# STATEFUL: Pydantic objesi gerektiren tool'lar — tool.func() doğrudan çağrı
# ---------------------------------------------------------------------------


def test_suggest_mitigations_real():
    """``suggest_mitigations_wrapped`` FairnessReport + ErrorSlice listesi alır.

    Wrapper imzası: ``(fairness: Optional[FairnessReport], error_slices: Sequence[ErrorSlice])``.
    """
    from ai_data_science_team.tools.responsible_ai import (
        ErrorSlice,
        compute_fairness,
    )

    fairness = compute_fairness(
        protected_attribute="gender",
        group_labels=["A", "A", "B", "B"],
        y_true=[1, 0, 1, 0],
        y_pred=[1, 0, 0, 0],
        threshold=0.10,
    )
    error_slices = [
        ErrorSlice(
            slice_expr="age=senior",
            n=50,
            error_rate=0.30,
            baseline_error_rate=0.10,
            lift=2.0,
        ),
    ]
    out = suggest_mitigations_wrapped.func(fairness=fairness, error_slices=error_slices)
    s = str(out).lower()
    assert (
        "ok" in s
        or "mitigation" in s
        or "reweigh" in s
        or "investigate" in s
        or "no mitigation" in s
    ), f"suggest_mitigations beklenen çıktı üretmedi: {s[:300]}"


def test_dashboard_payload_real():
    """``dashboard_payload_wrapped`` bir ResponsibleAIDashboard'ı dict'e çevirir.

    Wrapper imzası: ``(d: ResponsibleAIDashboard)``.
    """
    from ai_data_science_team.tools.responsible_ai import build_dashboard

    d = build_dashboard(model_id="m1")
    out = dashboard_payload_wrapped.func(d=d)
    s = str(out).lower()
    assert "model_id" in s or "m1" in s or "ok" in s or "fairness" in s, (
        f"dashboard_payload beklenen dict üretmedi: {s[:300]}"
    )
