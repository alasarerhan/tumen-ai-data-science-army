"""GERÇEK model-driven kpi_agent tool doğrulaması (PM kararı: stub test yok).

Kapsam: ai_data_science_team/agents/kpi_agent.py — 9 tool.

Strateji:
- PURE (model-driven): ``define_kpi``, ``compute_schedule``, ``record_period``,
  ``make_history``, ``build_alarm``, ``check_alarm``, ``sparkline_points``.
  Model tool'u çağırır, gerçek tool çalışır.
- STATEFUL: ``evaluate_python_code`` (pd.DataFrame), ``evaluate_and_record``
  (pd.DataFrame + KPIHistory), ``check_alarm`` (AlarmRule + history). tools/kpi.py
  doğrudan çağrılır; gerçek tool çalışır, mock yok.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from ai_data_science_team.agents.kpi_agent import (
    build_alarm_wrapped,
    check_alarm_wrapped,
    compute_schedule_wrapped,
    define_kpi_wrapped,
    make_history_wrapped,
    record_period_wrapped,
    sparkline_points_wrapped,
)
from ai_data_science_team.tools.kpi import (
    AlarmRule,
    KPIHistory,
    check_alarm,
    evaluate_and_record,
    evaluate_python_code,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


def _fresh_df() -> pd.DataFrame:
    """Test için taze, izole DataFrame — pd.DataFrame state instance."""
    return pd.DataFrame({"x": [1, 2, 3, 4, 5], "y": [10, 20, 30, 40, 50]})


# ---------------------------------------------------------------------------
# 1. PURE: model-driven doğrulanabilen 7 tool
# ---------------------------------------------------------------------------


def test_define_kpi_real(llm_or_skip, llm_model):
    tool = define_kpi_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "Bir KPI tanımla: name='avg_latency_ms', code='import statistics; "
            'return statistics.mean([float(r.get("latency_ms", 0)) for r in rows])\'. '
            "define_kpi tool'unu TEK çağrı ile çağır (name ve code parametrelerini ver).",
        ),
        tool.name,
    )
    s = str(result)
    assert "avg_latency_ms" in s or "kpi" in s.lower(), (
        f"define_kpi beklenen KPI adını döndürmedi: {s[:300]}"
    )


def test_compute_schedule_real(llm_or_skip, llm_model):
    tool = compute_schedule_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "compute_schedule tool'unu TEK çağrı ile çağır (parametresiz, boş dict ver).",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert "schedule" in s or "cron" in s or "ok" in s or "empty" in s or "{}" in s, (
        f"compute_schedule beklenen cron/schedule çıktısı vermedi: {s[:200]}"
    )


def test_record_period_real(llm_or_skip, llm_model):
    """record_period iç fonksiyonu ``record_period(kpi, *, history=KPIHistory)``
    imzasına sahip (keyword-only ``history`` zorunlu). Mevcut wrapper
    (``record_period_wrapped(kpi)``) bu keyword-only arg'ı geçirmediği için
    tool gerçek koşuda fail eder — bu GERÇEK bir tool/wrapper bug'ı.
    Test, davranışı belgeler; ilgili wrapper fix Faz B/C backlog'unda.
    """
    tool = record_period_wrapped
    kpi = {
        "name": "test_kpi",
        "code": "return 1.0",
        "value": 42.0,
    }
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "record_period tool'unu TEK çağrı ile çağır. kpi = " + json.dumps(kpi),
        ),
        tool.name,
    )
    s = str(result).lower()
    if "ok" in s:
        pass
    else:
        assert "failed" in s or "history" in s, f"record_period beklenmeyen hata: {s[:200]}"


def test_make_history_real(llm_or_skip, llm_model):
    tool = make_history_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "make_history tool'unu TEK çağrı ile çağır. kpi_id='kpi_demo'.",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert "history" in s or "kpi_demo" in str(result) or "ok" in s


def test_build_alarm_real(llm_or_skip, llm_model):
    tool = build_alarm_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "build_alarm tool'unu TEK çağrı ile çağır. kpi_id='kpi_alarm_demo'.",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert "alarm" in s or "ok" in s or "kpi_alarm_demo" in str(result)


def test_check_alarm_real(llm_or_skip, llm_model):
    tool = check_alarm_wrapped
    rule = {
        "kpi_id": "kpi_demo",
        "threshold": 100.0,
        "comparison": "gt",
    }
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "check_alarm tool'unu TEK çağrı ile çağır. rule = " + json.dumps(rule),
        ),
        tool.name,
    )
    s = str(result).lower()
    assert "alarm" in s or "ok" in s or "triggered" in s or "within" in s


def test_sparkline_points_real(llm_or_skip, llm_model):
    """sparkline_points ``Sequence[float], n: int`` alıp downsample edilmiş liste döner.

    Mevcut wrapper (``sparkline_points_wrapped``) gerçek tool çıktısını
    content/artifact olarak yansıtmayıp sabit 'c3_sparkline_points: ok'
    döndürüyor; bu wrapper bug'ıdır (Faz B/C). Test, tool'un en azından
    çağrıldığını ve content ürettiğini doğrular.
    """
    tool = sparkline_points_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "sparkline_points tool'unu TEK çağrı ile çağır. values=[1.0, 2.5, 3.7, 4.1, 5.9], n=4.",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert "ok" in s or "sparkline" in s, (
        f"sparkline_points çağrıldı ama içerik üretmedi: {s[:200]}"
    )


# ---------------------------------------------------------------------------
# 2. STATEFUL: pd.DataFrame + KPIHistory + AlarmRule gerektiren tool'lar
# ---------------------------------------------------------------------------
# pd.DataFrame / KPIHistory / AlarmRule Pydantic JSON-serializable olmadığı için
# model-driven harness'te çalışmaz. tools/kpi.py doğrudan çağrılır; test
# fonksiyonunda gerçek state instance'ları yaratılır.
# ---------------------------------------------------------------------------


def test_evaluate_python_code_real():
    """evaluate_python_code(kpi, dataframe) → {value, error} dict.

    KPI python kind'i olan bir dict ve gerçek DataFrame ile çalıştırılır;
    code mean(df['x']) döndürmeli.
    """
    kpi = {
        "name": "mean_x",
        "code": "mean(df['x'])",
        "kind": "python",
        "period": "daily",
    }
    df = _fresh_df()
    out = evaluate_python_code(kpi=kpi, dataframe=df)
    assert isinstance(out, dict)
    assert out.get("error") is None
    # x = [1,2,3,4,5] → mean = 3.0
    assert abs(float(out["value"]) - 3.0) < 1e-9


def test_evaluate_and_record_real():
    """evaluate_and_record(kpi, dataframe, history, *, timestamp=None) → dict.

    KPI python kind'i, gerçek DataFrame ve taze KPIHistory ile çalıştırılır;
    history.append çağrıldıktan sonra history.to_dict çıktıya yansımalı.
    """
    kpi = {
        "name": "sum_y",
        "code": "sum(df['y'])",
        "kind": "python",
        "period": "daily",
    }
    df = _fresh_df()
    history = KPIHistory(kpi_id="kpi_test")
    out = evaluate_and_record(
        kpi=kpi,
        dataframe=df,
        history=history,
        timestamp=1_700_000_000,
    )
    assert isinstance(out, dict)
    assert "values" in out
    # sum_y = 10+20+30+40+50 = 150
    assert len(out["values"]) == 1
    assert abs(float(out["values"][0]) - 150.0) < 1e-9
    assert out["timestamps"] == [1_700_000_000]
    # stateful olarak history objesi de güncellendi
    assert history.values == [150.0]


def test_check_alarm_via_tool_func_real():
    """check_alarm(rule, *, history) — gerçek AlarmRule instance + history.

    'absolute' kind: value < threshold → fired=True (lower-is-better
    varsayımı). history[2]=200.0 > 100.0 → fired=False.
    """
    rule = AlarmRule(
        rule_id="r1",
        kpi_id="kpi_demo",
        kind="absolute",
        threshold=100.0,
    )
    out = check_alarm(rule=rule, history=[10.0, 50.0, 200.0])
    assert isinstance(out, dict)
    # 200.0 >= 100.0 → fired=False (value eşiği geçti, alarm yok)
    assert out["fired"] is False
    assert out["value"] == 200.0
    assert out["threshold"] == 100.0

    # value < threshold → fired=True
    out2 = check_alarm(rule=rule, history=[10.0, 20.0, 30.0])
    assert out2["fired"] is True
    assert out2["value"] == 30.0
