"""
Tests for ``ai_data_science_team.tools.g2_retrain_orchestrator`` (G2 tool layer).
"""

from __future__ import annotations



from ai_data_science_team.tools.g2_retrain_orchestrator import (
    build_audit_trail,
    build_policy,
    decide_action,
    event_to_dict,
    record_event,
    simulate,
)


def _no_drift_signal():
    return {
        "feature_report": {"overall_drift": "none"},
        "performance": None,
        "metric_name": "roc_auc",
        "feature_drift_trigger": False,
        "performance_trigger": False,
        "should_retrain": False,
    }


def _drift_signal(feature=True, perf=True, delta_pct=-0.07):
    return {
        "feature_report": {"overall_drift": "significant" if feature else "none"},
        "performance": {
            "baseline": 0.80,
            "current": 0.80 + delta_pct,
            "delta": delta_pct,
            "delta_pct": delta_pct / 0.80,
            "threshold_breached": perf,
            "improved": False,
            "lower_is_better": False,
            "relative_threshold": 0.05,
            "absolute_threshold": None,
        },
        "metric_name": "roc_auc",
        "feature_drift_trigger": feature,
        "performance_trigger": perf,
        "should_retrain": feature or perf,
    }


class TestBuildPolicy:
    def test_default_policy_when_no_triggers(self):
        policy = build_policy({"name": "p1"})
        assert policy.name == "p1"
        assert len(policy.triggers) >= 1
        assert policy.require_hitl_approval is True

    def test_explicit_triggers(self):
        spec = {
            "name": "drift-and-metric",
            "triggers": [
                {"kind": "drift", "feature_drift": True},
                {
                    "kind": "metric-drop",
                    "performance_drift": True,
                    "relative_threshold": 0.05,
                    "on_metric": "roc_auc",
                },
            ],
        }
        policy = build_policy(spec)
        assert len(policy.triggers) == 2
        # Triggers preserved verbatim.
        kinds = [t.kind for t in policy.triggers]
        assert kinds == ["drift", "metric-drop"]

    def test_serialise_roundtrip(self):
        policy = build_policy(
            {
                "name": "rt",
                "triggers": [{"kind": "drift", "feature_drift": True}],
                "action": "monitor",
                "require_hitl_approval": False,
            }
        )
        round = policy.to_dict()
        assert round["name"] == "rt"
        assert round["action"] == "monitor"
        assert round["require_hitl_approval"] is False


class TestDecideAction:
    def test_no_trigger_with_clean_signal(self):
        policy = build_policy(
            {"name": "any-drift", "triggers": [{"kind": "drift", "feature_drift": True}]}
        )
        out = decide_action(_no_drift_signal(), policy)
        assert out["should_trigger"] is False
        assert out["action"] == "monitor"

    def test_trigger_on_drift(self):
        policy = build_policy(
            {"name": "any-drift", "triggers": [{"kind": "drift", "feature_drift": True}]}
        )
        sig = _drift_signal(feature=True, perf=False)
        out = decide_action(sig, policy)
        assert out["should_trigger"] is True
        assert "drift" in out["triggered_by"]

    def test_trigger_on_performance_only(self):
        policy = build_policy(
            {
                "name": "metric-only",
                "triggers": [
                    {
                        "kind": "metric-drop",
                        "performance_drift": True,
                        "relative_threshold": 0.05,
                        "on_metric": "roc_auc",
                    }
                ],
            }
        )
        sig = _drift_signal(feature=False, perf=True, delta_pct=-0.10)
        out = decide_action(sig, policy)
        assert out["should_trigger"] is True

    def test_no_trigger_performance_under_threshold(self):
        policy = build_policy(
            {
                "name": "metric-only",
                "triggers": [
                    {
                        "kind": "metric-drop",
                        "performance_drift": True,
                        "relative_threshold": 0.10,
                        "on_metric": "roc_auc",
                    }
                ],
            }
        )
        sig = _drift_signal(feature=False, perf=True, delta_pct=-0.005)
        out = decide_action(sig, policy)
        assert out["should_trigger"] is False

    def test_returned_payload_includes_action(self):
        policy = build_policy(
            {"name": "p", "triggers": [{"kind": "drift", "feature_drift": True}]}
        )
        out = decide_action(_no_drift_signal(), policy)
        for key in ("should_trigger", "action", "triggered_by", "policy_name", "require_hitl_approval"):
            assert key in out


class TestSimulate:
    def test_no_triggers_with_clean_signals(self):
        policy = build_policy(
            {"name": "any", "triggers": [{"kind": "drift", "feature_drift": True}]}
        )
        signals = [_no_drift_signal() for _ in range(10)]
        result = simulate(signals, policy)
        assert result["n_signals"] == 10
        assert result["n_triggers"] == 0

    def test_counts_triggers(self):
        policy = build_policy(
            {"name": "any", "triggers": [{"kind": "drift", "feature_drift": True}]}
        )
        signals = [
            _no_drift_signal(),
            _drift_signal(feature=True, perf=False),
            _drift_signal(feature=True, perf=False),
            _drift_signal(),
        ]
        result = simulate(signals, policy)
        assert result["n_signals"] == 4
        assert result["n_triggers"] >= 2

    def test_cooldown_suppresses_back_to_back_triggers(self):
        # 60-second spacing → cooldown 3600 s ⇒ only one trigger.
        policy = build_policy(
            {
                "name": "cooldown-test",
                "triggers": [
                    {
                        "kind": "drift",
                        "feature_drift": True,
                        "cooldown_s": 3600.0,
                    }
                ],
            }
        )
        signals = [_drift_signal(feature=True, perf=False)] * 5
        result = simulate(signals, policy)
        assert result["n_triggers"] == 1


class TestAuditTrail:
    def test_record_event_returns_event_dict(self):
        policy = build_policy({"name": "p"})
        signal = _drift_signal()
        decision = decide_action(signal, policy)
        ev = record_event(policy, signal, decision, notes=["first event"])
        out = event_to_dict(ev)
        assert out["policy_name"] == "p"
        assert "first event" in out["notes"]

    def test_build_audit_trail_orders_by_timestamp(self):
        policy = build_policy({"name": "p"})
        ev_late = record_event(
            policy,
            _drift_signal(),
            decide_action(_drift_signal(), policy),
            timestamp=200,
        )
        ev_early = record_event(
            policy,
            _drift_signal(),
            decide_action(_drift_signal(), policy),
            timestamp=100,
        )
        trail = build_audit_trail([ev_late, ev_early])
        assert trail[0]["timestamp"] == 100
        assert trail[1]["timestamp"] == 200

    def test_decision_carry_hitl_flag(self):
        policy = build_policy(
            {
                "name": "hitl",
                "triggers": [{"kind": "drift", "feature_drift": True}],
                "require_hitl_approval": False,
            }
        )
        sig = _drift_signal(feature=True, perf=False)
        decision = decide_action(sig, policy)
        assert decision["require_hitl_approval"] is False
        assert decision["should_trigger"] is True
