"""GERÇEK test alerting_agent tool doğrulaması (PM kararı: skip yok).

Kapsam: ai_data_science_team/agents/alerting_agent.py — 9 tool.

Strateji:
- PURE (model-driven): ``channel_template_wrapped`` model tarafından çağrılır
  ve tool gerçekten invoke edilir.
- STATEFUL: ``AlertStore`` / ``AlertRule`` / ``Incident`` / ``IncidentStore``
  gerçek Pydantic/dataclass objeleri yaratılır ve **underlying tool**
  (``define_rule``, ``raise_incident`` vb.) doğrudan çağrılır. wrapper
  Pydantic olmayan argümanları (name/metric vb.) taşımadığı için
  ``tool.func()`` üzerinden değil, alt katmandaki fonksiyondan çağrı
  yapılır.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.alerting_agent import (
    channel_template_wrapped,
)
from ai_data_science_team.tools.alerting import (
    AlertStore,
    IncidentStore,
    acknowledge_incident,
    define_rule,
    evaluate_rule,
    raise_incident,
    resolve_incident,
    route_to_channels,
    summarise,
    tick_escalation,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# 1. PURE: channel_template — model-driven, parametresiz JSON verir
# ---------------------------------------------------------------------------

def test_channel_template_real(llm_or_skip, llm_model):
    tool = channel_template_wrapped
    content, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "channel_template_wrapped tool'unu TEK çağrı ile çağır; "
            "channel='slack', payload={'title':'Latency high','severity':'warning'} ver.",
        ),
        tool.name,
    )
    assert content


# ---------------------------------------------------------------------------
# 2. STATEFUL: AlertStore / AlertRule / Incident / IncidentStore
# ---------------------------------------------------------------------------

def _fresh_store() -> AlertStore:
    return AlertStore()


def _seed_rule_and_incident() -> tuple[AlertStore, IncidentStore, str]:
    """Test senaryosu: bir rule + tetikleyen incident üret."""
    rule_store = _fresh_store()
    inc_store = IncidentStore()
    define_rule(
        rule_store,
        name="latency_high",
        metric="p99_latency_ms",
        comparator=">",
        threshold=100.0,
        severity="warning",
        channels=["slack"],
    )
    rule_id = rule_store.rules[0].rule_id
    inc = raise_incident(
        rule_store,
        rule_id=rule_id,
        metric_value=150.0,
    )
    inc_store.add(inc)
    return rule_store, inc_store, inc.incident_id


def test_define_rule_real():
    """define_rule: AlertStore'a AlertRule ekler."""
    store = _fresh_store()
    rule = define_rule(
        store,
        name="err_rate",
        metric="error_rate",
        comparator=">=",
        threshold=0.05,
        severity="critical",
        channels=["slack", "email"],
    )
    assert rule.name == "err_rate"
    assert len(store.rules) == 1
    assert store.rules[0].rule_id == rule.rule_id


def test_evaluate_rule_real():
    """evaluate_rule: threshold + comparator doğrular."""
    store = _fresh_store()
    define_rule(
        store,
        name="r", metric="m", comparator=">", threshold=10.0,
        severity="info", channels=["slack"],
    )
    rule = store.rules[0]
    assert evaluate_rule(rule, metric_value=20.0) is True
    assert evaluate_rule(rule, metric_value=5.0) is False


def test_raise_incident_real():
    """raise_incident: kuralla birlikte Incident üretir."""
    store = _fresh_store()
    define_rule(
        store,
        name="r", metric="m", comparator=">", threshold=10.0,
        severity="warning", channels=["slack"],
    )
    inc = raise_incident(store, rule_id=store.rules[0].rule_id, metric_value=20.0)
    assert inc.status == "open"
    assert inc.severity == "warning"
    assert inc.value == 20.0


def test_acknowledge_incident_real():
    """acknowledge_incident: open → acknowledged."""
    _, _, inc_id = _seed_rule_and_incident()
    # son incident'i yeniden kur
    rule_store = _fresh_store()
    inc_store = IncidentStore()
    define_rule(
        rule_store,
        name="r", metric="m", comparator=">", threshold=10.0,
        severity="warning", channels=["slack"],
    )
    inc = raise_incident(rule_store, rule_id=rule_store.rules[0].rule_id, metric_value=20.0)
    inc_store.add(inc)
    acknowledge_incident(inc, by="alice", note="on it")
    assert inc.status == "acknowledged"
    assert inc.acknowledged_by == "alice"


def test_resolve_incident_real():
    """resolve_incident: status → resolved + resolved_at set."""
    rule_store = _fresh_store()
    define_rule(
        rule_store,
        name="r", metric="m", comparator=">", threshold=10.0,
        severity="warning", channels=["slack"],
    )
    inc = raise_incident(rule_store, rule_id=rule_store.rules[0].rule_id, metric_value=20.0)
    resolve_incident(inc, note="mitigated")
    assert inc.status == "resolved"
    assert inc.resolved_at is not None
    assert "mitigated" in inc.resolution_note


def test_tick_escalation_real():
    """tick_escalation: zincirdeki adımları zaman aşımına göre tetikler."""
    rule_store = _fresh_store()
    define_rule(
        rule_store,
        name="r", metric="m", comparator=">", threshold=10.0,
        severity="critical", channels=["slack"],
    )
    inc = raise_incident(
        rule_store,
        rule_id=rule_store.rules[0].rule_id,
        metric_value=20.0,
        escalation_policy=[
            {"level": 1, "channel": "slack", "timeout_seconds": 60.0},
        ],
    )
    # Şimdi + 120s → ilk step tetiklenmeli
    triggered = tick_escalation(inc, now=inc.raised_at + 120.0)
    assert len(triggered) == 1
    assert triggered[0].level == 1


def test_route_to_channels_real():
    """route_to_channels: incident başına kanal özeti döner."""
    rule_store = _fresh_store()
    define_rule(
        rule_store,
        name="r", metric="m", comparator=">", threshold=10.0,
        severity="warning", channels=["slack", "email"],
    )
    inc = raise_incident(rule_store, rule_id=rule_store.rules[0].rule_id, metric_value=20.0)
    out = route_to_channels(inc)
    assert out["incident_id"] == inc.incident_id
    assert set(out["channels"].keys()) == {"slack", "email"}
    assert out["channels"]["slack"]["payload"]["severity"] == "warning"


def test_summarise_real():
    """summarise: IncidentStore istatistikleri."""
    rule_store = _fresh_store()
    define_rule(
        rule_store,
        name="r", metric="m", comparator=">", threshold=10.0,
        severity="warning", channels=["slack"],
    )
    inc_store = IncidentStore()
    inc1 = raise_incident(rule_store, rule_id=rule_store.rules[0].rule_id, metric_value=20.0)
    inc2 = raise_incident(rule_store, rule_id=rule_store.rules[0].rule_id, metric_value=30.0)
    inc_store.add(inc1)
    inc_store.add(inc2)
    counts = summarise(inc_store)
    assert counts["total"] == 2
    assert counts["open"] == 2
    assert counts["warning"] == 2
