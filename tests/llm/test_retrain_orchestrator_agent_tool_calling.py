"""GERÇEK retrain_orchestrator_agent tool doğrulaması (PM kararı: stub test yok).

Kapsam: ai_data_science_team/agents/retrain_orchestrator_agent.py — 6 tool.

Strateji:
- PURE (model-driven): ``build_policy`` model tarafından çağrılır.
- STATEFUL: ``decide_action``, ``simulate``, ``record_event``, ``event_to_dict``,
  ``build_audit_trail`` tools/retrain_orchestrator.py doğrudan çağrılır;
  gerçek Policy / Event instance'ları test'te yaratılır.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.retrain_orchestrator_agent import (
    build_policy_wrapped,
)
from ai_data_science_team.tools.retrain_orchestrator import (
    Event,
    Policy,
    build_audit_trail,
    decide_action,
    event_to_dict,
    record_event,
    simulate,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


def _fresh_policy() -> Policy:
    """Test için taze Policy — gerçek dataclass, tetikleyici'siz."""
    return Policy(
        name="drift-driven",
        triggers=[],
        action="retrain",
        require_hitl_approval=False,
    )


# ---------------------------------------------------------------------------
# 1. PURE: build_policy — model-driven doğrulanabilir
# ---------------------------------------------------------------------------


def test_build_policy_real(llm_or_skip, llm_model):
    tool = build_policy_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            (
                "build_policy_wrapped tool'unu TEK çağrı ile çağır; "
                "spec={'name':'drift','metric':'psi','threshold':0.2} ver."
            ),
        ),
        tool.name,
    )
    assert content
    assert artifact is not None


# ---------------------------------------------------------------------------
# 2. STATEFUL: Policy / Event gerektiren tool'lar — tools/retrain_orchestrator.py
# ---------------------------------------------------------------------------


def test_decide_action_real():
    """decide_action(signal, policy) → {should_trigger, action, triggered_by, ...}.

    Boş trigger listesi olan bir policy için hiçbir signal tetiklemez;
    should_trigger=False, action='monitor'.
    """
    policy = _fresh_policy()
    signal = {
        "feature_drift_trigger": True,
        "performance_trigger": True,
        "performance": {"threshold_breached": True, "delta_pct": 0.1},
    }
    out = decide_action(signal=signal, policy=policy)
    assert isinstance(out, dict)
    assert "should_trigger" in out
    assert "action" in out
    assert "triggered_by" in out
    # triggers=[] → hiçbir signal tetiklemez
    assert out["should_trigger"] is False
    assert out["action"] == "monitor"
    assert out["policy_name"] == "drift-driven"


def test_simulate_real():
    """simulate(signals, policy) → {n_signals, n_triggers, decisions, ...}."""
    policy = _fresh_policy()
    # triggers=[] olduğu için hiçbir signal tetiklemez; n_triggers=0 beklenir.
    signals = [{"feature_drift_trigger": True}, {"feature_drift_trigger": True}]
    out = simulate(signals=signals, policy=policy)
    assert isinstance(out, dict)
    assert out["n_signals"] == 2
    assert out["n_triggers"] == 0
    assert isinstance(out["decisions"], list)
    assert len(out["decisions"]) == 2
    # Her kararda should_trigger=False (triggers=[])
    for d in out["decisions"]:
        assert d["should_trigger"] is False


def test_record_event_real():
    """record_event(policy, signal, decision, *, ...) → Event dataclass.

    Gerçek Event instance üretir; signal/decision dict kopyalanır.
    """
    policy = _fresh_policy()
    signal = {"feature_drift_trigger": True}
    decision = {"should_trigger": True, "action": "retrain"}
    ev = record_event(
        policy=policy,
        signal=signal,
        decision=decision,
        notes=["baseline-check"],
    )
    assert isinstance(ev, Event)
    assert ev.policy_name == "drift-driven"
    assert ev.signal == {"feature_drift_trigger": True}
    assert ev.decision == {"should_trigger": True, "action": "retrain"}
    assert ev.notes == ["baseline-check"]
    assert ev.id  # uuid üretildi
    assert ev.timestamp > 0


def test_event_to_dict_real():
    """event_to_dict(ev) → {id, timestamp, policy_name, signal, decision, notes}."""
    ev = Event(
        id="ev-1",
        timestamp=1_700_000_000.0,
        policy_name="drift-driven",
        signal={"x": 1},
        decision={"should_trigger": False},
        notes=["n1"],
    )
    out = event_to_dict(ev=ev)
    assert isinstance(out, dict)
    assert out["id"] == "ev-1"
    assert out["timestamp"] == 1_700_000_000.0
    assert out["policy_name"] == "drift-driven"
    assert out["signal"] == {"x": 1}
    assert out["decision"] == {"should_trigger": False}
    assert out["notes"] == ["n1"]


def test_build_audit_trail_real():
    """build_audit_trail(events) → events.timestamp'a göre sıralanmış dict listesi."""
    ev1 = Event(id="a", timestamp=200.0, policy_name="p", signal={}, decision={})
    ev2 = Event(id="b", timestamp=100.0, policy_name="p", signal={}, decision={})
    ev3 = Event(id="c", timestamp=300.0, policy_name="p", signal={}, decision={})
    trail = build_audit_trail(events=[ev1, ev2, ev3])
    assert isinstance(trail, list)
    assert [e["id"] for e in trail] == ["b", "a", "c"]
    # Her biri event_to_dict çıktısı
    for entry in trail:
        assert "timestamp" in entry
        assert "signal" in entry
        assert "decision" in entry
