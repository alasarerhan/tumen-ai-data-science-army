from __future__ import annotations

from platform_api.services.runtime_engine_parity_service import build_runtime_engine_parity_report


def test_runtime_engine_parity_harness_maps_platform_lifecycle_surfaces() -> None:
    report = build_runtime_engine_parity_report()

    assert report["status"] == "passed"
    assert report["promotion_decision"] == "do_not_promote_default_until_reviewed"
    assert report["runtime_result"]["status"] == "completed"
    assert report["cancel_result"]["status"] == "cancelled"
    assert report["checks"] == {
        "runtime_completed": True,
        "logs_mapped": True,
        "signals_mapped": True,
        "artifacts_mapped": True,
        "retry_mapped": True,
        "cancel_mapped": True,
        "scheduler_non_replacement_recorded": True,
    }
    assert report["surface_mapping"]["logs"]["target_contract"] == "/v1/runs/{id}/logs"
    assert report["surface_mapping"]["signals"]["target_contract"] == "/v1/runs/{id}/signals"
    assert report["surface_mapping"]["artifacts"]["target_contract"] == "/v1/artifacts"
    assert report["surface_mapping"]["retry"]["covered"] is True
    assert report["surface_mapping"]["cancel"]["covered"] is True
