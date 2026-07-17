"""Tests for G7 Alerting / Incident tool."""
from __future__ import annotations

import pytest

import ai_data_science_team.tools.alerting as g7


@pytest.fixture
def rules():
    return g7.AlertStore()


@pytest.fixture
def drift_rule(rules):
    return g7.define_rule(
        rules,
        name="data_drift_high",
        metric="psi",
        comparator=">",
        threshold=0.20,
        severity="warning",
        channels=["slack", "email"],
        description="PSI exceeds 0.20",
    )


@pytest.fixture
def incidents():
    return g7.IncidentStore()


class TestDefineRule:
    def test_returns_rule(self, rules):
        r = g7.define_rule(
            rules, name="x", metric="psi",
            comparator=">", threshold=0.2,
            severity="warning", channels=["slack"],
        )
        assert r.rule_id != ""
        assert r.name == "x"
        assert r.severity == "warning"

    def test_invalid_comparator(self, rules):
        with pytest.raises(ValueError):
            g7.define_rule(
                rules, name="x", metric="psi",
                comparator="~~", threshold=0.2,
                severity="warning", channels=["slack"],
            )

    def test_invalid_severity(self, rules):
        with pytest.raises(ValueError):
            g7.define_rule(
                rules, name="x", metric="psi",
                comparator=">", threshold=0.2,
                severity="fatal", channels=["slack"],
            )

    def test_invalid_channel(self, rules):
        with pytest.raises(ValueError):
            g7.define_rule(
                rules, name="x", metric="psi",
                comparator=">", threshold=0.2,
                severity="warning", channels=["pigeon"],
            )

    def test_lookup_by_id(self, rules, drift_rule):
        r = rules.by_id(drift_rule.rule_id)
        assert r is drift_rule
        assert rules.by_id("nope") is None


class TestEvaluateRule:
    def test_triggers_when_above(self, drift_rule):
        assert g7.evaluate_rule(drift_rule, metric_value=0.25) is True

    def test_not_triggered_when_below(self, drift_rule):
        assert g7.evaluate_rule(drift_rule, metric_value=0.10) is False

    def test_at_threshold_not_triggered(self, drift_rule):
        # comparator ">" so 0.20 == 0.20 → False
        assert g7.evaluate_rule(drift_rule, metric_value=0.20) is False


class TestRaiseIncident:
    def test_raises_when_triggered(self, rules, drift_rule, incidents):
        inc = g7.raise_incident(
            rules, rule_id=drift_rule.rule_id, metric_value=0.30,
        )
        incidents.add(inc)
        assert inc.severity == "warning"
        assert inc.status == "open"
        assert "slack" in inc.channels_notified
        assert "email" in inc.channels_notified

    def test_raises_with_escalation(self, rules, drift_rule):
        inc = g7.raise_incident(
            rules, rule_id=drift_rule.rule_id, metric_value=0.30,
            escalation_policy=[
                {"level": 1, "channel": "slack", "timeout_seconds": 60},
                {"level": 2, "channel": "email", "timeout_seconds": 300},
            ],
        )
        assert len(inc.escalation) == 2
        assert inc.escalation[0].level == 1
        assert inc.escalation[0].timeout_seconds == 60

    def test_unknown_rule(self, rules):
        with pytest.raises(KeyError):
            g7.raise_incident(rules, rule_id="nope", metric_value=0.5)

    def test_rule_not_triggered(self, rules, drift_rule):
        with pytest.raises(ValueError):
            g7.raise_incident(
                rules, rule_id=drift_rule.rule_id, metric_value=0.05,
            )


class TestAckResolve:
    def test_acknowledge_open(self, rules, drift_rule, incidents):
        inc = g7.raise_incident(
            rules, rule_id=drift_rule.rule_id, metric_value=0.30,
        )
        incidents.add(inc)
        g7.acknowledge_incident(inc, by="alice", note="on it")
        assert inc.status == "acknowledged"
        assert inc.acknowledged_by == "alice"
        assert "ack@alice" in inc.resolution_note

    def test_acknowledge_after_ack(self, rules, drift_rule):
        inc = g7.raise_incident(
            rules, rule_id=drift_rule.rule_id, metric_value=0.30,
        )
        g7.acknowledge_incident(inc, by="alice")
        g7.acknowledge_incident(inc, by="bob", note="second")
        # acks can be re-issued; should not raise
        assert inc.status == "acknowledged"

    def test_acknowledge_resolved_raises(self, rules, drift_rule):
        inc = g7.raise_incident(
            rules, rule_id=drift_rule.rule_id, metric_value=0.30,
        )
        g7.resolve_incident(inc)
        with pytest.raises(ValueError):
            g7.acknowledge_incident(inc, by="alice")

    def test_resolve_sets_status(self, rules, drift_rule):
        inc = g7.raise_incident(
            rules, rule_id=drift_rule.rule_id, metric_value=0.30,
        )
        g7.resolve_incident(inc, note="fixed upstream")
        assert inc.status == "resolved"
        assert inc.resolved_at is not None
        assert "resolved" in inc.resolution_note

    def test_resolve_already_resolved_is_noop(self, rules, drift_rule):
        inc = g7.raise_incident(
            rules, rule_id=drift_rule.rule_id, metric_value=0.30,
        )
        g7.resolve_incident(inc, note="first")
        first_resolved_at = inc.resolved_at
        g7.resolve_incident(inc, note="second")
        assert inc.resolved_at == first_resolved_at


class TestEscalation:
    def test_tick_no_elapsed(self, rules, drift_rule):
        inc = g7.raise_incident(
            rules, rule_id=drift_rule.rule_id, metric_value=0.30,
            escalation_policy=[
                {"level": 1, "channel": "slack", "timeout_seconds": 60},
            ],
        )
        triggered = g7.tick_escalation(inc, now=inc.raised_at + 10)
        assert triggered == []

    def test_tick_triggers_step(self, rules, drift_rule):
        inc = g7.raise_incident(
            rules, rule_id=drift_rule.rule_id, metric_value=0.30,
            escalation_policy=[
                {"level": 1, "channel": "slack", "timeout_seconds": 60},
            ],
        )
        triggered = g7.tick_escalation(inc, now=inc.raised_at + 61)
        assert len(triggered) == 1
        assert triggered[0].level == 1
        assert triggered[0].triggered is True

    def test_tick_chained_steps(self, rules, drift_rule):
        inc = g7.raise_incident(
            rules, rule_id=drift_rule.rule_id, metric_value=0.30,
            escalation_policy=[
                {"level": 1, "channel": "slack", "timeout_seconds": 60},
                {"level": 2, "channel": "email", "timeout_seconds": 120},
            ],
        )
        # After 70s only level 1 fires
        t1 = g7.tick_escalation(inc, now=inc.raised_at + 70)
        assert len(t1) == 1 and t1[0].level == 1
        # After another 130s level 2 fires (130 > 120)
        t2 = g7.tick_escalation(inc, now=inc.raised_at + 200)
        assert len(t2) == 1 and t2[0].level == 2

    def test_resolved_stops_escalation(self, rules, drift_rule):
        inc = g7.raise_incident(
            rules, rule_id=drift_rule.rule_id, metric_value=0.30,
            escalation_policy=[
                {"level": 1, "channel": "slack", "timeout_seconds": 60},
            ],
        )
        g7.resolve_incident(inc)
        triggered = g7.tick_escalation(inc, now=inc.raised_at + 9999)
        assert triggered == []


class TestChannelRouting:
    def test_route_no_send_fn(self, rules, drift_rule):
        inc = g7.raise_incident(
            rules, rule_id=drift_rule.rule_id, metric_value=0.30,
        )
        result = g7.route_to_channels(inc)
        assert "slack" in result["channels"]
        assert result["channels"]["slack"]["delivered"] is False

    def test_route_with_send_fn(self, rules, drift_rule):
        sent_to: list = []
        def send(channel, payload):
            sent_to.append(channel)

        inc = g7.raise_incident(
            rules, rule_id=drift_rule.rule_id, metric_value=0.30,
        )
        result = g7.route_to_channels(inc, send_fn=send)
        assert sent_to == ["slack", "email"]
        assert result["channels"]["slack"]["delivered"] is True

    def test_route_send_fn_raises_captured(self, rules, drift_rule):
        def send(channel, payload):
            raise RuntimeError("upstream down")

        inc = g7.raise_incident(
            rules, rule_id=drift_rule.rule_id, metric_value=0.30,
        )
        result = g7.route_to_channels(inc, send_fn=send)
        assert result["channels"]["slack"]["delivered"] is False
        assert "upstream down" in result["channels"]["slack"]["error"]

    def test_channel_template_slack(self):
        s = g7.channel_template("slack", {
            "incident_id": "i1", "severity": "warning",
            "metric": "psi", "value": 0.3,
            "comparator": ">", "threshold": 0.2,
            "status": "open",
        })
        assert "warning" in s
        assert "psi" in s

    def test_channel_template_email(self):
        s = g7.channel_template("email", {
            "incident_id": "i1", "severity": "critical",
            "metric": "psi", "value": 0.3,
            "comparator": ">", "threshold": 0.2,
            "status": "open",
        })
        assert "Subject: [CRITICAL]" in s

    def test_channel_template_webhook(self):
        import json
        s = g7.channel_template("webhook", {
            "incident_id": "i1", "severity": "critical",
            "metric": "psi", "value": 0.3,
            "comparator": ">", "threshold": 0.2,
            "status": "open",
        })
        parsed = json.loads(s)
        assert parsed["incident_id"] == "i1"
        assert parsed["value"] == 0.3

    def test_channel_template_unknown(self):
        with pytest.raises(ValueError):
            g7.channel_template("carrier_pigeon", {})


class TestIncidentStore:
    def test_filter_status(self, rules, drift_rule, incidents):
        i1 = g7.raise_incident(rules, rule_id=drift_rule.rule_id,
                                metric_value=0.30)
        i2 = g7.raise_incident(rules, rule_id=drift_rule.rule_id,
                                metric_value=0.50)
        incidents.add(i1)
        incidents.add(i2)
        g7.acknowledge_incident(i1, by="alice")
        assert len(incidents.filter(status="acknowledged")) == 1
        assert len(incidents.filter(status="open")) == 1


class TestSummarise:
    def test_basic(self, rules, drift_rule, incidents):
        i1 = g7.raise_incident(rules, rule_id=drift_rule.rule_id,
                                metric_value=0.30)
        i2 = g7.raise_incident(rules, rule_id=drift_rule.rule_id,
                                metric_value=0.50)
        incidents.add(i1)
        incidents.add(i2)
        g7.resolve_incident(i2)
        s = g7.summarise(incidents)
        assert s["total"] == 2
        assert s["open"] == 1
        assert s["resolved"] == 1
        assert s["warning"] == 2

    def test_empty(self, incidents):
        s = g7.summarise(incidents)
        assert s["total"] == 0

