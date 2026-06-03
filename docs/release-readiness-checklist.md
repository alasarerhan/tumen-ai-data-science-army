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
| Known blockers / expected skips | 11 platform API skips; plugin tests require workspace-local basetemp on Windows. GA still requires release metadata, monitoring/rollback owners, verified security finding closure, and advanced runtime lifecycle parity before promotion. |

## 3. Evidence Matrix

| Gate | Command or check | Preconditions confirmed | Evidence location / output | Owner | Status |
|------|------------------|-------------------------|----------------------------|-------|--------|
| Frontend typecheck | `cd frontend && npm run typecheck` | [x] | 2026-06-03 passed | Local | Passed |
| Frontend lint | `cd frontend && npm run lint` | [x] | 2026-06-03 passed with 15 warnings | Local | Passed with warnings |
| Frontend unit tests | `cd frontend && npm run test` | [x] | 2026-06-03 35 files / 228 tests passed | Local | Passed |
| Backend pytest | `cd apps/platform-api-app && python -m pytest -q` | [x] | 2026-06-03 684 passed / 11 skipped | Local | Passed |
| Agent-library pytest | root/plugin selected suites | [x] | 2026-06-03 root 94 passed; selected plugins 353 passed | Local | Passed |
| Playwright golden path | `cd frontend && npm run test:e2e` | [x] | 2026-06-03 `npm.cmd run test:e2e -- --reporter=line`; 24/24 passed | Local | Passed |
| Backend smoke | `/healthz`, `/ready`, `/metrics`, auth path, `/v1/me` | [x] | 2026-06-03 `/healthz`, `/ready`, `/metrics` returned 200; Vite proxy dev login returned 200; proxy `/v1/me` returned 200 | Local | Passed |
| Frontend smoke | app load, login path, workflow/run path | [x] | 2026-06-03 frontend root returned 200 on 127.0.0.1:5174; Playwright covered login, dashboard, AI workspace, workflow designer, and runs-list navigation | Local | Passed |
| SQL Server data source | structured form, secret-safe API response, connection test | [x] | 2026-06-03 targeted backend/frontend tests and mocked SQL Server connection smoke passed; durable encrypted secret store added | Local | Passed |
| Settings configuration center | Workspace+User+Admin categories and read-only unsupported settings | [x] | 2026-06-03 category navigation/read-only status test passed; unsupported persistence remains intentionally not invented | Local | Passed |
| Migration check | `cd apps/platform-api-app && python -m alembic upgrade head` | [x] | 2026-06-03 upgraded through `0018_data_source_secrets` | Local | Passed |

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
| Advanced runtime adapter seam present | service-layer test reference | `test_run_orchestration_service.py`; `docs/m22-lifecycle-parity-matrix.md` |
| Production-safe agent catalog registered at startup | startup wiring test/reference | |
| `ContextStore` backing decision recorded | doc/test/reference for selected backend | |
| Signal parity mapped to production event path | signal create/consume test reference | |
| Execution mode fail-closed in release profile | config and mode-selection tests | |
| Lifecycle parity verified | success/failure/logs/signals/artifacts/retry-cancel matrix | `docs/m22-lifecycle-parity-matrix.md`; decision is no default promotion until endpoint/parity harness exists |

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
| SQL Server secret storage durability | Medium | Platform | fix | 2026-06-03 | Fixed by `0018_data_source_secrets`, `platform_api/services/secret_store_service.py`, and `tests/test_data_sources_sql_server.py` |
| Security verified findings remain open | Critical | Platform security | fix | 2026-06-03 | `security-report/verified-findings.md` |
| RuntimeEngine default promotion deferred | Medium | Platform architecture | defer | 2026-06-03 | `docs/m22-lifecycle-parity-matrix.md` |
