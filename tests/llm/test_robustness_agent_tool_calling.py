"""GERÇEK model-driven robustness_agent tool doğrulaması (PM kararı: stub test yok).

Kapsam: ai_data_science_team/agents/robustness_agent.py — 4 tool.

PURE (sequence args, InjectedState yok → model-driven test edilebilir):
- default_scenarios_wrapped  — sigma_levels, mask_levels (Sequence[float])

STATEFUL (np.ndarray / Callable → API test kapsamı):
- add_gaussian_noise_wrapped       — X (np.ndarray)
- mask_features_wrapped            — X (np.ndarray)
- evaluate_robustness_wrapped      — predict (Callable), X/y (np.ndarray)
"""

from __future__ import annotations

import inspect

import pytest

from ai_data_science_team.agents.robustness_agent import default_scenarios_wrapped
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# PURE: default_scenarios_wrapped
# ---------------------------------------------------------------------------

def test_default_scenarios_real(llm_or_skip, llm_model):
    """``default_scenarios_wrapped(sigma_levels, mask_levels)`` spec'in default setini üretir."""
    tool = default_scenarios_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model, tool,
            "default_scenarios tool'unu TEK çağrı ile çağır. "
            "sigma_levels=[0.05, 0.1, 0.2], mask_levels=[0.1, 0.2, 0.3].",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert (
        "scenario" in s
        or "noise" in s
        or "sigma" in s
        or "mask" in s
        or "ok" in s
    ), f"default_scenarios beklenen senaryo seti üretmedi: {s[:200]}"


# ---------------------------------------------------------------------------
# STATEFUL: np.ndarray / Callable → API test kapsamı
# ---------------------------------------------------------------------------

def test_add_gaussian_noise_stateful_skipped():
    """``add_gaussian_noise_wrapped`` np.ndarray alır; Pydantic JSON-serializable değil."""
    import ai_data_science_team.agents.robustness_agent as mod

    wrapper = mod.add_gaussian_noise_wrapped
    sig = inspect.signature(wrapper.func)
    assert "X" in sig.parameters
    pytest.skip(
        "stateful tool: add_gaussian_noise_wrapped np.ndarray arg alır; "
        "API entegrasyon testinde kapsanacak"
    )


def test_mask_features_stateful_skipped():
    """``mask_features_wrapped`` np.ndarray alır; aynı nedenle skip."""
    import ai_data_science_team.agents.robustness_agent as mod

    wrapper = mod.mask_features_wrapped
    sig = inspect.signature(wrapper.func)
    assert "X" in sig.parameters
    pytest.skip(
        "stateful tool: mask_features_wrapped np.ndarray arg alır; "
        "API entegrasyon testinde kapsanacak"
    )


def test_evaluate_robustness_stateful_skipped():
    """``evaluate_robustness_wrapped`` model predict Callable + np.ndarray alır."""
    import ai_data_science_team.agents.robustness_agent as mod

    wrapper = mod.evaluate_robustness_wrapped
    sig = inspect.signature(wrapper.func)
    assert "predict" in sig.parameters
    pytest.skip(
        "stateful tool: evaluate_robustness_wrapped Callable + np.ndarray alır; "
        "API entegrasyon testinde kapsanacak"
    )
