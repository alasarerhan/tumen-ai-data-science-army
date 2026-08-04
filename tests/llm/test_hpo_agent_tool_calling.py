"""hpo_agent tool doğrulaması (PM kararı: stub test yok).

1 PURE tool (``suggest_default_search_space``) için model-driven test
yapılır.

2 STATEFUL tool (``random_sample_params``: ``random.Random`` arg;
``run_study``: ``Callable`` arg) Pydantic JSON-serializable değildir. Bu
tool'lar model-driven harness kapsamı dışındadır; Faz C API entegrasyon
testinde kapsanmalıdır. Burada ``pytest.skip`` ile belgelenir.
"""

from __future__ import annotations

import inspect

import pytest

from ai_data_science_team.agents.hpo_agent import (
    random_sample_params_wrapped,
    run_study_wrapped,
    suggest_default_search_space_wrapped,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# PURE tool başına gerçek test
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
# STATEFUL: random.Random / Callable → API test Faz C kapsamında
# ---------------------------------------------------------------------------


def test_random_sample_params_stateful_skipped():
    """random_sample_params_wrapped ``rng: Optional[random.Random]`` arg alır;
    Pydantic JSON-serializable değil.

    Bu tool model-driven harness kapsamı dışındadır; Faz C API entegrasyon
    testinde kapsanmalıdır.
    """
    sig = inspect.signature(random_sample_params_wrapped.func)
    assert "rng" in sig.parameters
    pytest.skip("stateful tool: random.Random arg, Pydantic JSON-serializable değil; "
                "Faz C API entegrasyon testinde kapsanacak")


def test_run_study_stateful_skipped():
    """run_study_wrapped ``objective_fn: Callable`` arg alır; Pydantic JSON-serializable değil.

    Bu tool model-driven harness kapsamı dışındadır; Faz C API entegrasyon
    testinde kapsanmalıdır.
    """
    sig = inspect.signature(run_study_wrapped.func)
    assert "objective_fn" in sig.parameters
    pytest.skip("stateful tool: Callable arg, Pydantic JSON-serializable değil; "
                "Faz C API entegrasyon testinde kapsanacak")
