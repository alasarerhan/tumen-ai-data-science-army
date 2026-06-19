# M22 Runtime Lifecycle & Parity

> Consolidated note on the M22 advanced orchestration facade and its production-readiness status.
> Replaces `docs/m22-lifecycle-parity-matrix.md` and `apps/platform-api-app/docs/m22_orchestration_status.md`.

## Decision

`staged_m22` / `RuntimeEngine` is **not promoted** to the default production execution mode in this release.

The canonical production API remains `/v1/runs` through `platform_api.services.run_orchestration_service` and the Prefect gateway. The M22 facade remains staged infrastructure with local/staging-only guards. A tenant-admin parity endpoint now exists for review evidence, but it does not promote RuntimeEngine to the default execution path.

## Current State

| Surface | Status | Notes |
|---|---|---|
| `POST /v1/runs` | Integrated | Uses `platform_api.services.run_orchestration_service`; route contract is stable while internal execution is mode-selected |
| Run log streaming | Integrated with fallback | `platform_api.routes.logs` prefers Prefect-backed logs and only falls back to mock SSE when the upstream source is unavailable |
| `agent_registry.py` | Integrated at startup | Production-safe catalog is registered during app startup for discovery and staged M22 rollout |
| `runtime_engine.py` | Staged | Implemented and tested, not wired into the production request path |
| `orchestrator_agent.py` | Staged | Implemented and tested, not wired into the production request path |
| `context_store.py` | Redis-backed in staged mode | `staged_m22` runtime state now expects Redis-backed session persistence via platform API runtime-state selection |
| `workflow_resolver.py` | Staged | Implemented and tested, not wired into the production request path |
| `signals.py` | Bridged in staged mode | Production `workflow_signal_events` are mirrored into the staged M22 signal store for runtime consumption when `staged_m22` is enabled |

## Newly Integrated Guard Rails

- `platform_api.services.run_orchestration_service` now selects an execution adapter behind the stable `/v1/runs` API.
- `prefect` remains the default execution mode.
- `staged_m22` is now an explicit local/staging-only mode. Release profile rejects it fail-closed until lifecycle parity is proven.
- `staged_m22` currently bootstraps Redis-backed `ContextStore` session metadata around the canonical run creation path instead of replacing the execution engine outright.
- Production signal writes now mirror into the staged M22 `SignalStore` using the run's canonical orchestration session id.
- `/v1/admin/runtime-engine/parity` is tenant-admin gated and returns a deterministic harness report with `promotion_decision=do_not_promote_default_until_reviewed`.

## Parity Coverage

| Lifecycle surface | Production path evidence | M22 staged evidence | Promotion decision |
|---|---|---|---|
| Run creation success | `test_create_orchestration_run_id_returns_gateway_run_id` | `TestRuntimeEngineSuccess` in `test_m22_orchestration.py` | Covered separately; no default promotion |
| Run creation failure | `test_create_orchestration_run_id_raises_http_exception_when_fallback_disabled` | `TestRuntimeEngineFailure` | Covered separately; no default promotion |
| Local fallback safety | `test_create_orchestration_run_id_returns_local_fallback_when_enabled`; release fallback blocked in logs tests | RuntimeEngine graceful degradation tests | Covered separately; release fallback remains fail-closed |
| Logs | `test_logs_release_fallback.py` | RuntimeEngine parity harness maps step logs to `/v1/runs/{id}/logs` contract shape | Mapped for review; no default promotion |
| Signals / cancel | `test_signal_service.py`; workflow signal route coverage | RuntimeEngine parity harness maps node signal events and cancel behavior | Mapped for review; endpoint bridge remains staged-only |
| Artifacts / context | Platform artifact tests tracked in release checklist | RuntimeEngine parity harness maps context-store artifacts to `/v1/artifacts` contract target | Mapped for review; production artifact writes remain canonical |
| Retry / resume | `test_workflow_ir_v2.py` retry failed node coverage | RuntimeEngine parity harness includes retry probe and maps to node retry contract target | Mapped for review; no default promotion |
| Scheduler-adjacent behavior | `test_schedule_parser.py`, admin scheduler contract | RuntimeEngine parity harness records scheduler non-replacement decision | Keep Prefect/scheduler path canonical |

## Evidence Run

| Area | Command | Result |
|---|---|---|
| M22 RuntimeEngine primitives | `python -m pytest plugins/tests/test_m22_orchestration.py -q` | 84 passed |
| Platform run/log/signal/scheduler-adjacent behavior | `cd apps/platform-api-app && python -m pytest tests/test_run_orchestration_service.py tests/test_logs_release_fallback.py tests/test_signal_service.py tests/test_workflow_ir_v2.py tests/test_schedule_parser.py tests/test_admin_contract.py -q` | 90 passed, 1 skipped |
| RuntimeEngine platform parity harness | `cd apps/platform-api-app && python -m pytest tests/test_runtime_engine_parity_service.py tests/test_admin_contract.py::test_runtime_engine_parity_report_is_tenant_admin_readable tests/test_admin_contract.py::test_admin_and_finops_routes_require_tenant_admin -q` | 3 passed |

## Integration Recommendation

**Keep and integrate deliberately.** The accurate statement is now:

- Canonical orchestration is already live.
- Advanced M22 execution remains staged infrastructure.

## Integration Checklist

- [x] Keep `/v1/runs` as the canonical production orchestration API
- [x] Route production run creation through `run_orchestration_service` and the Prefect gateway
- [x] Prefer Prefect-backed log streaming before any local/mock fallback
- [x] Add M22 imports to `platform-api-app` where the advanced facade replaces or augments the current gateway path
- [x] Create execution endpoints or a parity harness that explicitly exercise `RuntimeEngine`
- [x] Register the production agent catalog in `AgentRegistry` at startup
- [x] Finalize `ContextStore` persistence backing as `Redis`
- [x] Connect `SignalStore` to `workflow_signal_events` through staged-mode mirroring
- [x] Add explicit local/staging-only execution mode for staged M22 rollout
- [x] Keep frontend orchestration UX on `/v1/runs` while internal adapter rollout proceeds

## Required Future Work Before Default Promotion

- Review the tenant-admin `/v1/admin/runtime-engine/parity` report before any default promotion decision.
- Keep mapping RuntimeEngine logs, signals, artifacts, retry/cancel, and scheduler-adjacent behavior to current platform API contracts as RuntimeEngine integration deepens.
- Re-run the platform and M22 suites with a release-like runtime-state backend.
- Update this matrix before changing `orchestration_execution_mode` defaults.

## Related

- `STRATEGY.md` Section 3 (Phase 4)
- `ai_data_science_team/orchestration.py`
- `platform_api/services/run_orchestration_service.py`
- `platform_api/services/runtime_engine_parity_service.py`
- `platform_api/routes/admin.py`
- `platform_api/routes/logs.py`
- `plugins/tests/test_m22_orchestration.py`
- `docs/RELEASE.md` §5 Advanced Orchestration Gate

---

**Source consolidation note**

- `docs/m22-lifecycle-parity-matrix.md` → §Decision, §Parity Coverage, §Evidence Run, §Required Future Work.
- `apps/platform-api-app/docs/m22_orchestration_status.md` → §Current State, §Newly Integrated Guard Rails, §Integration Recommendation, §Integration Checklist, §Related.
