# M22 Orchestration Layer Status

- Status: Canonical API path integrated; advanced M22 facade still staged
- Date: 2026-04-27
- Owners: Platform Architecture

## Summary

The repo now has two separate truths that must not be conflated:

1. The production orchestration path is integrated through the canonical `POST /v1/runs` API and the Prefect gateway.
2. The richer M22 facade primitives (`AgentRegistry`, `RuntimeEngine`, `OrchestratorAgent`, `ContextStore`, `WorkflowResolver`, `SignalStore`) are implemented and tested, and part of that surface is now entering production through a guarded adapter seam.

The earlier "built, not yet integrated" wording was therefore too broad. It still applies to the advanced M22 facade, but it no longer accurately describes the platform's canonical orchestration entrypoint.

## Current State

| Surface | Status | Notes |
|--------|--------|-------|
| `POST /v1/runs` | Integrated | Uses `platform_api.services.run_orchestration_service`; route contract is stable while internal execution is mode-selected |
| Run log streaming | Integrated with fallback | `platform_api.routes.logs` prefers Prefect-backed logs and only falls back to mock SSE when the upstream source is unavailable |
| `agent_registry.py` | Integrated at startup | Production-safe catalog is registered during app startup for discovery and staged M22 rollout |
| `runtime_engine.py` | Staged | Implemented and tested, not wired into the production request path |
| `orchestrator_agent.py` | Staged | Implemented and tested, not wired into the production request path |
| `context_store.py` | Redis-backed in staged mode | `staged_m22` runtime state now expects Redis-backed session persistence via platform API runtime-state selection |
| `workflow_resolver.py` | Staged | Implemented and tested, not wired into the production request path |
| `signals.py` | Bridged in staged mode | Production `workflow_signal_events` are mirrored into the staged M22 signal store for runtime consumption when `staged_m22` is enabled |

## 2026-06-03 Lifecycle Parity Decision

`staged_m22` is not promoted to the default production execution mode. The current evidence proves the canonical `/v1/runs` path and the M22 primitives independently, but logs/artifacts/signals/retry/scheduler behavior are not yet exercised through a single RuntimeEngine-backed platform lifecycle.

See `docs/m22-lifecycle-parity-matrix.md` for the parity matrix and command evidence.

## Newly Integrated Guard Rails

- `platform_api.services.run_orchestration_service` now selects an execution adapter behind the stable `/v1/runs` API.
- `prefect` remains the default execution mode.
- `staged_m22` is now an explicit local/staging-only mode. Release profile rejects it fail-closed until lifecycle parity is proven.
- `staged_m22` currently bootstraps Redis-backed `ContextStore` session metadata around the canonical run creation path instead of replacing the execution engine outright.
- Production signal writes now mirror into the staged M22 `SignalStore` using the run's canonical orchestration session id.

## Integration Path

Per `STRATEGY.md`, the advanced M22 facade remains a next-phase integration target:

```text
Sonraki öncelikler:
- Orkestrasyon Katmanı (M22): AgentRegistry + RuntimeEngine + OrchestratorAgent + WorkflowSignal
  — tüm agent'ları yönetecek altyapı; M21 ve M23-M25 için kritik ön bağımlılık.
```

## Decision: Keep or Remove?

### Option 1: Keep (Recommended)

Rationale:
- The code is implemented, tested, and documented.
- `STRATEGY.md` still points to the advanced facade as a planned integration step.
- The canonical `/v1/runs` path can continue to serve production while deeper orchestration capabilities are introduced deliberately.

Action: Keep the M22 facade and integrate it incrementally behind the canonical API.

### Option 2: Remove

Rationale:
- Reduces maintenance surface for staged code.
- Avoids confusion if no integration work is planned.

Action: Delete M22 facade modules and rebuild later if needed.

## Recommendation

Keep and integrate deliberately. The accurate statement is now:

- Canonical orchestration is already live.
- Advanced M22 execution remains staged infrastructure.

## Integration Checklist

- [x] Keep `/v1/runs` as the canonical production orchestration API
- [x] Route production run creation through `run_orchestration_service` and the Prefect gateway
- [x] Prefer Prefect-backed log streaming before any local/mock fallback
- [x] Add M22 imports to `platform-api-app` where the advanced facade replaces or augments the current gateway path
- [ ] Create execution endpoints or a parity harness that explicitly exercise `RuntimeEngine`
- [x] Register the production agent catalog in `AgentRegistry` at startup
- [x] Finalize `ContextStore` persistence backing as `Redis`
- [x] Connect `SignalStore` to `workflow_signal_events` through staged-mode mirroring
- [x] Add explicit local/staging-only execution mode for staged M22 rollout
- [x] Keep frontend orchestration UX on `/v1/runs` while internal adapter rollout proceeds

## Related

- `STRATEGY.md` Section 3
- `ai_data_science_team/orchestration.py`
- `platform_api/services/run_orchestration_service.py`
- `platform_api/routes/logs.py`
- `plugins/tests/test_m22_orchestration.py`
