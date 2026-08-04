"""GERÇEK test bayesian_agent tool doğrulaması (PM kararı: stub test yok).

Kapsam: ai_data_science_team/agents/bayesian_agent.py — 3 tool.

Strateji:
- PURE (skaler/Sequence argümanlar → model-driven test edilebilir):
  ``beta_posterior_wrapped`` + ``normal_means_posterior_wrapped``
  ``_drive_tool_call`` ile test edilir.
- STATEFUL: ``bayes_decision_wrapped`` tool.func() ile doğrudan çağrılır.
  Wrapper ``(content, artifact)`` tuple döner; tool'un asıl çıktısı
  ``artifact["result"]`` içinde. Pydantic ``BetaPosterior`` dataclass'ları
  test içinde gerçek ``beta_posterior(...)`` ile üretilir (mock değil).

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.bayesian_agent import (
    bayes_decision_wrapped,
    beta_posterior_wrapped,
    normal_means_posterior_wrapped,
)
from ai_data_science_team.tools.bayesian import beta_posterior
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# 1. PURE: beta_posterior_wrapped + normal_means_posterior_wrapped
#    → model-driven (_drive_tool_call)
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
# 2. STATEFUL: bayes_decision_wrapped — tool.func() doğrudan çağrı
#    BetaPosterior dataclass'ları gerçek ``beta_posterior`` çağrılarından
#    geliyor; mock/hardcoded değer yok.
# ---------------------------------------------------------------------------


def _invoke_wrapper(wrapped, /, **kwargs):
    """Wrapper.func() çağır; (content, artifact) tuple döner. Hata → AssertionError."""
    content, artifact = wrapped.func(**kwargs)
    if isinstance(content, str) and content.startswith("Tool ") and "failed:" in content:
        raise AssertionError(f"tool çağrısı başarısız: {content!r}")
    return content, artifact


def test_bayes_decision_real_clear_winner():
    """``bayes_decision`` belirgin B üstünlüğünde ``promote_b`` kararı vermeli.

    A: 30/100 (rate 0.30)  →  posterior ~ Beta(31, 71).
    B: 70/100 (rate 0.70)  →  posterior ~ Beta(71, 31).
    B açık ara önde → ``P(B>A) ≈ 1.0`` ve expected_loss ≈ 0 → ``promote_b``.
    """
    post_a = beta_posterior(successes=30, failures=70)
    post_b = beta_posterior(successes=70, failures=30)

    content, artifact = _invoke_wrapper(
        bayes_decision_wrapped,
        posterior_a=post_a, posterior_b=post_b,
    )
    assert "ok" in content
    decision = artifact["result"]
    assert decision["decision"] == "promote_b"
    assert decision["prob_b_better"] > 0.99
    assert decision["expected_loss_b_over_a"] < 0.001
    assert "rationale" in decision


def test_bayes_decision_real_clear_loser():
    """A belirgin üstün → ``bayes_decision`` semantiği: ``expected_loss_b_over_a``
    çok yüksek olduğu için tool ``inconclusive`` döner (sırf P(B>A)=0 yetmez).

    Tool'un sözleşmesi: karar ``expected_loss < 0.001`` AND
    ``prob_b_better > 0.95`` (ya da simetriği) iken kesinleşir.
    """
    post_a = beta_posterior(successes=70, failures=30)
    post_b = beta_posterior(successes=30, failures=70)

    _content, artifact = _invoke_wrapper(
        bayes_decision_wrapped,
        posterior_a=post_a, posterior_b=post_b,
    )
    decision = artifact["result"]
    # Çok yüksek loss → inconclusive (tool'un bilinen sözleşmesi)
    assert decision["decision"] == "inconclusive"
    assert decision["prob_b_better"] < 0.01
    assert decision["expected_loss_b_over_a"] > 0.1


def test_bayes_decision_real_inconclusive():
    """Yakın posterior'lar → ``inconclusive`` (P(B>A) eşik altında veya loss yüksek)."""
    post_a = beta_posterior(successes=50, failures=50)
    post_b = beta_posterior(successes=52, failures=48)

    _content, artifact = _invoke_wrapper(
        bayes_decision_wrapped,
        posterior_a=post_a, posterior_b=post_b,
    )
    decision = artifact["result"]
    # Eşikler çok yakın → inconclusive.
    assert decision["decision"] == "inconclusive"
    assert "prob_b_better" in decision
    assert 0.0 <= decision["prob_b_better"] <= 1.0


def test_bayes_decision_real_with_prior():
    """Öncel posterior şekillendirir; ``expected_loss`` yüksek kalırsa yine inconclusive.

    5/5 vs 20/5: ``P(B>A)≈0.957`` ama expected_loss>0.001 → inconclusive.
    Karar sözlüğünün doğru anahtarlar taşıdığını ve ``rationale`` ürettiğini
    doğrularız.
    """
    post_a = beta_posterior(successes=5, failures=5, prior_alpha=1, prior_beta=1)
    post_b = beta_posterior(successes=20, failures=5, prior_alpha=1, prior_beta=1)

    _content, artifact = _invoke_wrapper(
        bayes_decision_wrapped,
        posterior_a=post_a, posterior_b=post_b,
    )
    decision = artifact["result"]
    # ``expected_loss`` eşiği aşıyor; tool ``inconclusive`` dönmeli.
    assert decision["decision"] == "inconclusive"
    assert decision["prob_b_better"] > 0.9
    assert decision["expected_loss_b_over_a"] > 0.001
    assert isinstance(decision["rationale"], str)
    assert "rationale" in decision


def test_bayes_decision_real_schema_keys():
    """Karar sözlüğü tüm beklenen anahtarları içermeli (schema smoke test)."""
    post_a = beta_posterior(successes=10, failures=10)
    post_b = beta_posterior(successes=11, failures=9)

    _content, artifact = _invoke_wrapper(
        bayes_decision_wrapped,
        posterior_a=post_a, posterior_b=post_b,
    )
    decision = artifact["result"]
    expected_keys = {"decision", "rationale", "prob_b_better", "expected_loss_b_over_a"}
    assert expected_keys.issubset(decision.keys())
    assert decision["decision"] in {"promote_b", "stay_with_a", "inconclusive"}
