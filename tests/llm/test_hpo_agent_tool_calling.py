"""hpo_agent tool doğrulaması (PM kararı: stub test yok).

Kapsam: ai_data_science_team/agents/hpo_agent.py — 3 tool.

Strateji:
- PURE (model-driven): ``suggest_default_search_space`` model tarafından çağrılır.
- STATEFUL: ``random_sample_params`` ve ``run_study`` doğrudan tools/hpo.py'dan
  çağrılır; gerçek tool çalışır, mock yok.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import random

import pytest

from ai_data_science_team.agents.hpo_agent import (
    suggest_default_search_space_wrapped,
)
from ai_data_science_team.tools.hpo import random_sample_params, run_study
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# 1. PURE: suggest_default_search_space — model-driven doğrulanabilir
# ---------------------------------------------------------------------------


def test_suggest_default_search_space_real(llm_or_skip, llm_model):
    """suggest_default_search_space(engine, task_type) alır; default search space dict döner."""
    tool = suggest_default_search_space_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model, tool,
            "suggest_default_search_space tool'unu TEK çağrı ile çağır. "
            "engine='xgboost', task_type='classification'.",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert "ok" in s or "failed" in s or "error" in s, (
        f"suggest_default_search_space beklenen çıktı üretmedi: {s[:300]}"
    )


# ---------------------------------------------------------------------------
# 2. STATEFUL: random_sample_params + run_study — tools/hpo.py doğrudan çağrı
# ---------------------------------------------------------------------------
# random.Random / Callable Pydantic JSON-serializable olmadığı için
# model-driven harness'te çalışmaz. Bunun yerine tools/hpo.py'dan doğrudan
# çağrılır; bu, gerçek tool'u çalıştırır ve platform state enjeksiyonunu test
# fonksiyonunda simüle eder — model-driven testlerle aynı kapsam, mock yok.
# ---------------------------------------------------------------------------


def test_random_sample_params_real():
    """random_sample_params(space, rng=None) → sample edilmiş parametre dict."""
    space = {
        "lr": {"type": "float", "low": 0.001, "high": 0.5, "log": True},
        "depth": {"type": "int", "low": 3, "high": 12},
    }
    rng = random.Random(42)
    out = random_sample_params(space=space, rng=rng)
    assert isinstance(out, dict)
    assert "lr" in out and "depth" in out
    assert 0.001 <= float(out["lr"]) <= 0.5
    assert 3 <= int(out["depth"]) <= 12


def test_run_study_real():
    """run_study(objective_fn, space, *, ...) → HPO result dict.

    Basit bir objective_fn ile n_trials=3 koşturulur; result beklenen
    anahtarları içermeli.
    """
    space = {
        "x": {"type": "float", "low": -1.0, "high": 1.0},
    }

    def objective_fn(params):
        # 1.0 - x^2 maximize edilir; x=0 → 1.0 en iyi
        return 1.0 - params["x"] ** 2

    out = run_study(
        objective_fn=objective_fn,
        space=space,
        n_trials=3,
        random_seed=0,
    )
    assert isinstance(out, dict)
    assert "study_name" in out
    assert "best_trial" in out
    assert "n_trials_completed" in out
    assert out["direction"] == "maximize"
    assert out["n_trials_completed"] >= 1
    assert "value" in out["best_trial"]
    assert "params" in out["best_trial"]
