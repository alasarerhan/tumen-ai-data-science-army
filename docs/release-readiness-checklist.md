# Release Readiness Checklist

> Status: Active source of truth for the next release candidate.
>
> Use this file for release evidence. Do not use `docs/launch-checklist.md` as the active checklist.

## 1. Release Metadata

| Field | Value |
|------|-------|
| Release ID / version | |
| Target environment | |
| Release owner | |
| Frontend owner | |
| Backend owner | |
| On-call / rollback owner | |
| Planned freeze date | |
| Planned go/no-go date | |
| Linked release notes | |
| Linked rollback runbook | |

## 2. Verification Preconditions

Fill these before treating any command output below as reusable evidence.

| Precondition | Value |
|------|-------|
| Frontend env file / profile | Local Vite profile via `frontend/start_frontend_local.cmd` |
| Backend env file / profile | Local profile via `apps/platform-api-app/start_platform_api_local.cmd` |
| Auth mode (`dev` or `OIDC`) | `dev` for local verification; release profile guard tested |
| Database profile (`SQLite`, local Postgres, release-like Postgres) | SQLite local/temp DB for current local gates |
| Prefect status | Not live-smoked in this pass |
| Redis / context store status | Not live-smoked in this pass |
| Object/artifact storage status | Local artifact storage exercised by tests |
| Upload scanning dependency status | Not live-smoked in this pass |
| Frontend URL / port | Local launcher uses `http://127.0.0.1:5174` |
| Backend URL / port | Local launcher uses `http://127.0.0.1:8010` |
| External credentials or secrets required | Real LLM test skipped on OpenAI `insufficient_quota` |
| Known blockers / expected skips | Full Playwright suite still open; repeated local auth attempts can trip `/v1/auth/login/dev` rate limiting. 11 platform API skips; plugin tests require workspace-local basetemp on Windows |

## 3. Evidence Matrix

| Gate | Command or check | Preconditions confirmed | Evidence location / output | Owner | Status |
|------|------------------|-------------------------|----------------------------|-------|--------|
| Frontend typecheck | `cd frontend && npm run typecheck` | [x] | 2026-06-03 passed | Local | Passed |
| Frontend lint | `cd frontend && npm run lint` | [x] | 2026-06-03 passed with 15 warnings | Local | Passed with warnings |
| Frontend unit tests | `cd frontend && npm run test` | [x] | 2026-06-03 35 files / 226 tests passed | Local | Passed |
| Backend pytest | `cd apps/platform-api-app && python -m pytest -q` | [x] | 2026-06-03 684 passed / 11 skipped | Local | Passed |
| Agent-library pytest | root/plugin selected suites | [x] | 2026-06-03 root 94 passed; selected plugins 353 passed | Local | Passed |
| Playwright golden path | `cd frontend && npm run test:e2e` | [ ] | 2026-06-03 partial: login spec 3/4 passed in full-file run; isolated `already authenticated` test passed; full suite still pending | Local | Open |
| Backend smoke | `/healthz`, `/ready`, `/metrics`, auth path, `/v1/me` | [ ] | | | |
| Frontend smoke | app load, login path, workflow/run path | [ ] | 2026-06-03 app load OK on 127.0.0.1:5174; dev login and `/v1/me` verified through Vite proxy; workflow/run path still pending | Local | Partial |
| Migration check | `cd apps/platform-api-app && DATABASE_URL=sqlite:///./.tmp-migration-check.db python -m alembic upgrade head` | [x] | 2026-06-03 upgraded through `0017_workflow_ir_v2` | Local | Passed |

## 4. Release-Safety Checks

| Check | Expected evidence | Reference |
|------|-------------------|-----------|
| Release profile rejects dev auth | passing test or release-profile smoke result | |
| CSRF enforced for browser-mutating requests | frontend client evidence + backend validation evidence | |
| Tenant/workspace isolation verified | route matrix or scoped test references | |
| Admin / replay / cleanup actions role-gated | route or UI test references | |
| Health/readiness/metrics available | endpoint output or monitoring screenshot/log | |
| Structured error intake wired | client error reporting + backend intake reference | |

## 5. Advanced Orchestration Gate

Complete this section only if the release touches staged M22 or shared orchestration behavior.

| Check | Expected evidence | Reference |
|------|-------------------|-----------|
| `/v1/runs` public contract unchanged | route/service contract tests | |
| Advanced runtime adapter seam present | service-layer test reference | |
| Production-safe agent catalog registered at startup | startup wiring test/reference | |
| `ContextStore` backing decision recorded | doc/test/reference for selected backend | |
| Signal parity mapped to production event path | signal create/consume test reference | |
| Execution mode fail-closed in release profile | config and mode-selection tests | |
| Lifecycle parity verified | success/failure/logs/signals/artifacts/retry-cancel matrix | |

## 6. Monitoring and Rollback

| Item | Value |
|------|-------|
| Monitoring dashboard URL | |
| Error dashboard URL | |
| CI / build dashboard URL | |
| Status page or incident channel | |
| War room link / channel | |
| Rollback trigger summary | |
| Rollback command or procedure link | |
| Post-rollback verification steps | |

## 7. Sign-Off

| Role | Name | Decision | Date | Notes |
|------|------|----------|------|-------|
| Release owner | | | | |
| Frontend owner | | | | |
| Backend owner | | | | |
| Product / stakeholder | | | | |

## 8. Open Issues and Accepted Risk

| Issue | Severity | Owner | Decision (`fix`, `defer`, `accept`) | Date | Linked evidence |
|------|----------|-------|--------------------------------------|------|-----------------|
| | | | | | |
