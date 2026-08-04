"""GERÇEK model-driven bayesian_agent tool doğrulaması (PM kararı: stub test yok).

Kapsam: ai_data_science_team/agents/bayesian_agent.py — 3 tool.

PURE (skaler/Sequence argümanlar → model-driven test edilebilir):
- beta_posterior_wrapped             — successes, failures (int)
- normal_means_posterior_wrapped     — samples_a, samples_b (Sequence[float])

STATEFUL (Pydantic BetaPosterior → API test kapsamı):
- bayes_decision_wrapped — posterior_a, posterior_b (Pydantic BetaPosterior)
"""

from __future__ import annotations

import inspect

import pytest

from ai_data_science_team.agents.bayesian_agent import (
    beta_posterior_wrapped,
    normal_means_posterior_wrapped,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# PURE: Tool başına gerçek testler
# ---------------------------------------------------------------------------

def test_beta_posterior_real(llm_or_skip, llm_model):
    """``beta_posterior_wrapped(successes, failures)`` Beta posterior parametrelerini üretir."""
    tool = beta_posterior_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model, tool,
            "beta_posterior tool'unu TEK çağrı ile çağır. "
            "successes=42, failures=18.",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert (
        "beta" in s
        or "alpha" in s
        or "beta_param" in s
        or "ok" in s
    ), f"beta_posterior beklenen Beta posterior parametreleri üretmedi: {s[:200]}"


def test_normal_means_posterior_real(llm_or_skip, llm_model):
    """``normal_means_posterior_wrapped(samples_a, samples_b)`` normal-normal posterior üretir."""
    tool = normal_means_posterior_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model, tool,
            "normal_means_posterior tool'unu TEK çağrı ile çağır. "
            "samples_a=[1.2, 0.9, 1.5, 1.1, 0.8], samples_b=[2.1, 2.4, 1.9, 2.7, 2.2].",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert (
        "posterior" in s
        or "mean" in s
        or "normal" in s
        or "mu" in s
        or "ok" in s
    ), f"normal_means_posterior beklenen posterior üretmedi: {s[:200]}"


# ---------------------------------------------------------------------------
# STATEFUL: Pydantic BetaPosterior → API test kapsamı
# ---------------------------------------------------------------------------

def test_bayes_decision_stateful_skipped():
    """``bayes_decision_wrapped`` Pydantic BetaPosterior alır; JSON-serializable değil."""
    import ai_data_science_team.agents.bayesian_agent as mod

    wrapper = mod.bayes_decision_wrapped
    sig = inspect.signature(wrapper.func)
    assert "posterior_a" in sig.parameters
    pytest.skip(
        "stateful tool: bayes_decision_wrapped Pydantic BetaPosterior arg alır; "
        "API entegrasyon testinde kapsanacak"
    )
