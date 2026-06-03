# M22 Lifecycle Parity Matrix - 2026-06-03

## Decision

Do not promote `staged_m22` / `RuntimeEngine` to the default production execution mode in this release.

The canonical production API remains `/v1/runs` through `platform_api.services.run_orchestration_service` and the Prefect gateway. The M22 facade remains staged infrastructure with local/staging-only guards until an explicit RuntimeEngine execution endpoint or parity harness is implemented and reviewed.

## Evidence Run

| Area | Command | Result |
|------|---------|--------|
| M22 RuntimeEngine primitives | `python -m pytest plugins/tests/test_m22_orchestration.py -q` | 84 passed |
| Platform run/log/signal/scheduler-adjacent behavior | `cd apps/platform-api-app && python -m pytest tests/test_run_orchestration_service.py tests/test_logs_release_fallback.py tests/test_signal_service.py tests/test_workflow_ir_v2.py tests/test_schedule_parser.py tests/test_admin_contract.py -q` | 90 passed, 1 skipped |

## Parity Coverage

| Lifecycle surface | Production path evidence | M22 staged evidence | Promotion decision |
|-------------------|--------------------------|---------------------|--------------------|
| Run creation success | `test_create_orchestration_run_id_returns_gateway_run_id` | `TestRuntimeEngineSuccess` in `test_m22_orchestration.py` | Covered separately; no default promotion |
| Run creation failure | `test_create_orchestration_run_id_raises_http_exception_when_fallback_disabled` | `TestRuntimeEngineFailure` | Covered separately; no default promotion |
| Local fallback safety | `test_create_orchestration_run_id_returns_local_fallback_when_enabled`; release fallback blocked in logs tests | RuntimeEngine graceful degradation tests | Covered separately; release fallback remains fail-closed |
| Logs | `test_logs_release_fallback.py` | RuntimeEngine step logs in `RunResult` / `StepResult` tests | Not equivalent; needs endpoint-level mapping before promotion |
| Signals / cancel | `test_signal_service.py`; workflow signal route coverage | `TestRuntimeEngineSignals` cancel/skip/modify/annotate coverage | Covered separately; endpoint bridge remains staged-only |
| Artifacts / context | Platform artifact tests tracked in release checklist | `ContextStore` checkpoint/artifact tests in M22 suite | Not equivalent; needs production artifact mapping before promotion |
| Retry / resume | `test_workflow_ir_v2.py` retry failed node coverage | RuntimeEngine retry and circuit-breaker tests | Covered separately; no default promotion |
| Scheduler-adjacent behavior | `test_schedule_parser.py`, admin scheduler contract | Not a RuntimeEngine scheduler replacement | Keep Prefect/scheduler path canonical |

## Required Future Work Before Default Promotion

- Add an explicit RuntimeEngine execution endpoint or parity harness that exercises the staged runtime through the same observable lifecycle expected by `/v1/runs`.
- Map RuntimeEngine logs, signals, artifacts, retry/cancel, and scheduler-adjacent behavior to the current platform API contracts.
- Re-run the platform and M22 suites with a release-like runtime-state backend.
- Update `apps/platform-api-app/docs/m22_orchestration_status.md` and this matrix before changing `orchestration_execution_mode` defaults.
