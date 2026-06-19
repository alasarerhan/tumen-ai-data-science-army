# M22 Lifecycle Parity Matrix - 2026-06-03

## Decision

Do not promote `staged_m22` / `RuntimeEngine` to the default production execution mode in this release.

The canonical production API remains `/v1/runs` through `platform_api.services.run_orchestration_service` and the Prefect gateway. The M22 facade remains staged infrastructure with local/staging-only guards. A tenant-admin parity endpoint now exists for review evidence, but it does not promote RuntimeEngine to the default execution path.

## Evidence Run

| Area | Command | Result |
|------|---------|--------|
| M22 RuntimeEngine primitives | `python -m pytest plugins/tests/test_m22_orchestration.py -q` | 84 passed |
| Platform run/log/signal/scheduler-adjacent behavior | `cd apps/platform-api-app && python -m pytest tests/test_run_orchestration_service.py tests/test_logs_release_fallback.py tests/test_signal_service.py tests/test_workflow_ir_v2.py tests/test_schedule_parser.py tests/test_admin_contract.py -q` | 90 passed, 1 skipped |
| RuntimeEngine platform parity harness | `cd apps/platform-api-app && python -m pytest tests/test_runtime_engine_parity_service.py tests/test_admin_contract.py::test_runtime_engine_parity_report_is_tenant_admin_readable tests/test_admin_contract.py::test_admin_and_finops_routes_require_tenant_admin -q` | 3 passed |

## Parity Coverage

| Lifecycle surface | Production path evidence | M22 staged evidence | Promotion decision |
|-------------------|--------------------------|---------------------|--------------------|
| Run creation success | `test_create_orchestration_run_id_returns_gateway_run_id` | `TestRuntimeEngineSuccess` in `test_m22_orchestration.py` | Covered separately; no default promotion |
| Run creation failure | `test_create_orchestration_run_id_raises_http_exception_when_fallback_disabled` | `TestRuntimeEngineFailure` | Covered separately; no default promotion |
| Local fallback safety | `test_create_orchestration_run_id_returns_local_fallback_when_enabled`; release fallback blocked in logs tests | RuntimeEngine graceful degradation tests | Covered separately; release fallback remains fail-closed |
| Logs | `test_logs_release_fallback.py` | RuntimeEngine parity harness maps step logs to `/v1/runs/{id}/logs` contract shape | Mapped for review; no default promotion |
| Signals / cancel | `test_signal_service.py`; workflow signal route coverage | RuntimeEngine parity harness maps node signal events and cancel behavior | Mapped for review; endpoint bridge remains staged-only |
| Artifacts / context | Platform artifact tests tracked in release checklist | RuntimeEngine parity harness maps context-store artifacts to `/v1/artifacts` contract target | Mapped for review; production artifact writes remain canonical |
| Retry / resume | `test_workflow_ir_v2.py` retry failed node coverage | RuntimeEngine parity harness includes retry probe and maps to node retry contract target | Mapped for review; no default promotion |
| Scheduler-adjacent behavior | `test_schedule_parser.py`, admin scheduler contract | RuntimeEngine parity harness records scheduler non-replacement decision | Keep Prefect/scheduler path canonical |

## Required Future Work Before Default Promotion

- Review the tenant-admin `/v1/admin/runtime-engine/parity` report before any default promotion decision.
- Keep mapping RuntimeEngine logs, signals, artifacts, retry/cancel, and scheduler-adjacent behavior to current platform API contracts as RuntimeEngine integration deepens.
- Re-run the platform and M22 suites with a release-like runtime-state backend.
- Update `apps/platform-api-app/docs/m22_orchestration_status.md` and this matrix before changing `orchestration_execution_mode` defaults.
