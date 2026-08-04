"""GERÇEK model-driven eda tool doğrulaması (PM kararı D2).

Her eda tool'u için: gerçek model (ChatOpenAI) tool'a bind edilir, prompt ile
tool'u çağırması sağlanır, platform state'i (data_raw, InjectedState) enjekte
edilir, tool gerçekten çalıştırılır ve çıktı (content/artifact) doğrulanır.

Mock YOK. Stub YOK. RunnableLambda YOK. Tool başarısız olursa test FAIL eder.

Kapsam: ai_data_science_team/tools/eda.py — 6 tool.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.tools.eda import (
    describe_dataset,
    explain_data,
    generate_correlation_funnel,
    generate_dtale_report,
    generate_sweetviz_report,
    visualize_missing,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


def _prompt(instruction: str, columns: str) -> str:
    return (
        "Elinde bir DataFrame var. Sütunlar: "
        f"{columns}.\nGörev: {instruction}\n"
        "Uygun tool'u TEK çağrı ile çağır (gerekli parametreleri ver)."
    )


# ---------------------------------------------------------------------------
# Tool başına gerçek testler
# ---------------------------------------------------------------------------


def test_explain_data_real(llm_or_skip, llm_model, sample_data_dict, sample_df):
    tool = explain_data
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            _prompt(
                "Bu veri setini ayrıntılı şekilde açıkla (explain_data çağır, n_sample=5).",
                ", ".join(sample_df.columns),
            ),
            sample_data_dict,
        ),
        tool.name,
    )
    assert isinstance(result, (str, list)) and len(str(result)) > 0


def test_describe_dataset_real(llm_or_skip, llm_model, sample_data_dict, sample_df):
    tool = describe_dataset
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            _prompt(
                "Bu veri seti için istatistik özeti üret (describe_dataset çağır).",
                ", ".join(sample_df.columns),
            ),
            sample_data_dict,
        ),
        tool.name,
    )
    s = str(result).lower()
    assert any(
        k in s for k in ("row", "count", "mean", "describe", "summary", "statistic", "columns")
    ), f"describe_dataset beklenen eda çıktısı üretmedi: {s[:300]}"


def test_visualize_missing_real(llm_or_skip, llm_model, sample_data_dict, sample_df):
    tool = visualize_missing
    _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            _prompt(
                "Eksik veri analizi yap (visualize_missing çağır).", ", ".join(sample_df.columns)
            ),
            sample_data_dict,
        ),
        tool.name,
    )


def test_generate_correlation_funnel_real(llm_or_skip, llm_model, sample_data_dict, sample_df):
    tool = generate_correlation_funnel
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            _prompt(
                "Hedef sütun 'value' için korelasyon funnel üret "
                "(generate_correlation_funnel çağır, target='value').",
                ", ".join(sample_df.columns),
            ),
            sample_data_dict,
        ),
        tool.name,
    )
    assert result[1] if isinstance(result, tuple) else result, "korelasyon funnel artifact üretmeli"


def test_generate_sweetviz_report_real(  # noqa: E501
    llm_or_skip, llm_model, sample_data_dict, sample_df, tmp_path
):
    tool = generate_sweetviz_report
    _, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            _prompt(
                "sweetviz raporu üret (generate_sweetviz_report çağır; "
                f"report_directory='{tmp_path}', report_name='report.html').",
                ", ".join(sample_df.columns),
            ),
            sample_data_dict,
        ),
        tool.name,
    )
    if isinstance(artifact, dict):
        assert artifact, "sweetviz artifact boş"


def test_generate_dtale_report_real(llm_or_skip, llm_model, sample_data_dict, sample_df):
    tool = generate_dtale_report
    try:
        _assert_result(
            _drive_tool_call(
                llm_model,
                tool,
                _prompt(
                    "dtale ile interaktif analiz başlat (generate_dtale_report çağır, "
                    "host='localhost', port=40100, open_browser=False).",
                    ", ".join(sample_df.columns),
                ),
                sample_data_dict,
            ),
            tool.name,
        )
    finally:
        # dtale arka plan sunucusunu kapat (best-effort)
        try:
            import dtale

            for key in list(dtale.global_state.keys() or []):
                dtale.global_state.clear(key)
        except Exception:  # noqa: BLE001 — teardown best-effort
            pass
