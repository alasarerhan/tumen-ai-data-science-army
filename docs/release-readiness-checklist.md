# Release Readiness Checklist

> Status: Active source of truth for the next release candidate.
>
> Use this file for release evidence. Do not use `docs/launch-checklist.md` as the active checklist.

## 1. Release Metadata

| Field | Value |
|------|-------|
| Release ID / version | `design-partner-advanced-mvp-2026-06-04` |
| Target environment | Local/design-partner validation; not GA |
| Release owner | Platform Release Owner (role placeholder; named owner required before GA) |
| Frontend owner | Frontend Owner (role placeholder; named owner required before GA) |
| Backend owner | Backend/API Owner (role placeholder; named owner required before GA) |
| On-call / rollback owner | Platform On-call / Rollback Owner (role placeholder; named owner required before GA) |
| Planned freeze date | Not scheduled |
| Planned go/no-go date | Not scheduled |
| Linked release notes | `docs/release-notes-template.md` |
| Linked rollback runbook | `docs/release-readiness-checklist.md#6-monitoring-and-rollback` |

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
| Known blockers / expected skips | 11 platform API skips; plugin tests require workspace-local basetemp on Windows. GA still requires named release/monitoring/rollback owners and RuntimeEngine default-promotion review. VF-002 is closed by owner rotation attestation plus repo hygiene evidence; local provider liveness was not verified because this environment returned `URLError`. Universal Platform Control Plane foundation, DB-backed expansion, Agent Cockpit metrics, safe trace storage, Run Detail Trace Inspector with cost/token/evaluation/version/artifact previews, Workflow Run Matrix, Reports Artifact Lineage / Output Board, persisted ModelOps registry/monitor/deployment store, local CLI/MCP-ready adapters, tenant-admin trace cost/token FinOps summary, and RuntimeEngine parity harness are implemented. Live external Prefect connectivity, richer graph visualization, and LLM-assisted planner remain planned expansion work. |

## 3. Evidence Matrix

| Gate | Command or check | Preconditions confirmed | Evidence location / output | Owner | Status |
|------|------------------|-------------------------|----------------------------|-------|--------|
| Frontend typecheck | `cd frontend && npm run typecheck` | [x] | 2026-06-03 passed | Local | Passed |
| Frontend lint | `cd frontend && npm run lint` | [x] | 2026-06-04 passed with 14 warnings | Local | Passed with warnings |
| Frontend unit tests | `cd frontend && npm run test` | [x] | 2026-06-04 37 files / 243 tests passed | Local | Passed |
| Backend pytest | `cd apps/platform-api-app && rtk pytest -q` | [x] | 2026-06-04 717 passed | Local | Passed |
| Agent-library pytest | root/plugin selected suites | [x] | 2026-06-04 root 99 passed after sandbox and SQL-agent security regression coverage; selected plugins 353 passed | Local | Passed |
| Playwright golden path | `cd frontend && npm run test:e2e` | [x] | 2026-06-03 `npm.cmd run test:e2e -- --reporter=line`; 24/24 passed | Local | Passed |
| Backend smoke | `/healthz`, `/ready`, `/metrics`, auth path, `/v1/me` | [x] | 2026-06-03 `/healthz`, `/ready`, `/metrics` returned 200; Vite proxy dev login returned 200; proxy `/v1/me` returned 200 | Local | Passed |
| Frontend smoke | app load, login path, workflow/run path | [x] | 2026-06-03 frontend root returned 200 on 127.0.0.1:5174; Playwright covered login, dashboard, AI workspace, workflow designer, and runs-list navigation | Local | Passed |
| SQL Server data source | structured form, secret-safe API response, connection test | [x] | 2026-06-03 targeted backend/frontend tests and mocked SQL Server connection smoke passed; durable encrypted secret store added | Local | Passed |
| Settings configuration center | Workspace+User+Admin categories and read-only unsupported settings | [x] | 2026-06-03 category navigation/read-only status test passed; unsupported persistence remains intentionally not invented | Local | Passed |
| Migration check | `cd apps/platform-api-app && python -m alembic upgrade head` | [x] | 2026-06-09 temporary SQLite upgrade passed through `0021_modelops_production_store` | Local | Passed |
| Universal Platform Control Plane backend | catalog, query, policy/redaction, actions, chat routing, scheduler metadata, FinOps, artifact-backed ModelOps, docs search, adapter metadata, lineage relationships | [x] | 2026-06-04 `python -m pytest tests/test_control_plane.py tests/test_chat_service.py tests/test_runs_contract.py -q`; 39 passed | Local | Passed |
| Universal Platform Control Plane frontend | API client, renderer, relationship payload rendering, action confirmation, workflow route/detail fixes | [x] | 2026-06-04 targeted Vitest command passed 5 files / 27 tests; `npm.cmd run typecheck` passed | Local | Passed |
| Agent Cockpit first-pass frontend | Agents screen Control Plane `run.nodes` execution/failure/retry summary | [x] | 2026-06-04 `npm.cmd run test -- src/app/screens/Agents.test.tsx`; 5 passed; full frontend suite 37 files / 243 tests passed | Local | Passed |
| Agent execution trace storage | safe trace table, worker writes, run trace endpoint, Control Plane `agent.traces`, frontend typed client | [x] | 2026-06-04 targeted backend trace/control-plane tests passed; temporary SQLite `alembic upgrade head` passed through `0019_agent_execution_traces`; frontend `runs.test.ts` passed 7 tests | Local | Passed |
| Agent Run Detail first-pass frontend | Run Detail `Agent Traces` tab with safe trace metrics and rows | [x] | 2026-06-04 `npm.cmd run test -- src/app/screens/RunDetail.test.tsx src/app/hooks/useRuns.test.tsx src/app/api/runs.test.ts`; 3 files / 23 tests passed | Local | Passed |
| Agent Cockpit / Trace Inspector enrichment | Agents uses `run.nodes` + `agent.traces`; Run Detail selected trace inspector | [x] | 2026-06-04 `npm.cmd run test -- src/app/screens/Agents.test.tsx src/app/screens/RunDetail.test.tsx`; 2 files / 14 tests passed; typecheck passed; lint passed with 14 warnings | Local | Passed |
| Agent trace cost/token/evaluation/version/artifact previews | Safe trace metadata fields, Control Plane columns, Agent Cockpit metrics, Run Detail inspector previews | [x] | 2026-06-04 `python -m pytest -q tests/test_modelops.py tests/test_control_plane.py tests/test_workflow_ir_v2.py` passed 23 / skipped 1; `npm.cmd run test -- src/app/screens/Agents.test.tsx src/app/screens/RunDetail.test.tsx src/app/screens/ModelOps.test.tsx` passed 3 files / 15 tests; typecheck passed; lint passed with 14 existing warnings | Local | Passed |
| ModelOps first-pass surface | Artifact-backed registry, monitor snapshots, retrain candidates, frontend ModelOps screen | [x] | 2026-06-04 `/v1/modelops/summary`, Control Plane `modelops`, `/modelops` UI, migration check through `0020_agent_trace_metadata`, backend targeted set passed 23 / skipped 1, frontend targeted set passed 15 tests | Local | Passed |
| ModelOps production store and adapters | Persisted registry/monitor/deployment tables, admin-only write routes, persisted summary merge, local Control Plane CLI and stdio bridge | [x] | 2026-06-09 `python -m pytest -q apps/platform-api-app/tests/test_modelops.py apps/platform-api-app/tests/test_control_plane.py`; 14 passed. `python -m py_compile tools/platform_control_plane_cli.py tools/platform_control_plane_mcp_adapter.py`; passed. SQLite `alembic upgrade head` passed through `0021_modelops_production_store`. | Local | Passed |
| RuntimeEngine parity harness | tenant-admin read-only parity endpoint, lifecycle mapping, default promotion deferred | [x] | 2026-06-04 `python -m pytest tests/test_runtime_engine_parity_service.py tests/test_admin_contract.py::test_runtime_engine_parity_report_is_tenant_admin_readable tests/test_admin_contract.py::test_admin_and_finops_routes_require_tenant_admin -q`; 3 passed | Local | Passed |
| Workflow Run Matrix first-pass frontend | RunsList heatmap from run node executions | [x] | 2026-06-04 `npm.cmd run test -- src/app/screens/RunsList.test.tsx src/app/api/runs.test.ts`; 2 files / 14 tests passed; typecheck passed; lint passed with 14 warnings | Local | Passed |
| Artifact Lineage / Output Board first-pass | artifact list safe lineage fields, Reports grouped output board, Reports lineage graph | [x] | 2026-06-04 `pytest apps/platform-api-app/tests/test_artifact_service.py apps/platform-api-app/tests/test_artifacts_routes.py -q`; 18 passed. `npm.cmd run test -- src/app/screens/Reports.test.tsx`; 3 passed. Typecheck passed; lint passed with 14 warnings | Local | Passed |

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
| Lifecycle parity verified | success/failure/logs/signals/artifacts/retry-cancel matrix | `docs/m22-lifecycle-parity-matrix.md`; `/v1/admin/runtime-engine/parity`; decision remains no default promotion until reviewed |

## 6. Monitoring and Rollback

| Item | Value |
|------|-------|
| Monitoring dashboard URL | |
| Monitoring dashboard URL | Local: `/admin`, `/healthz`, `/ready`, `/metrics`; production dashboard URL required before GA |
| Error dashboard URL | Local: `/admin` error intake and structured logs; production error dashboard URL required before GA |
| CI / build dashboard URL | GitHub Actions workflow runs for `.github/workflows/ci.yml` and `.github/workflows/release-gates.yml` |
| Status page or incident channel | Platform incident channel placeholder; named channel required before GA |
| War room link / channel | Platform war-room placeholder; named link/channel required before GA |
| Rollback trigger summary | Trigger rollback when health/readiness fails, error rate breaches release SLO, or rollout monitor fails. |
| Rollback command or procedure link | Use `.github/workflows/rollout.yml` with `stage=rollback` and the last known good `version`; verify backend profile separately if backend deployment changes are included. |
| Post-rollback verification steps | Check `/healthz`, `/ready`, `/metrics`, login/dev or OIDC path, `/v1/me`, workflow list, latest run detail, admin scheduler/DLQ summary, and affected ModelOps/report artifact pages. |

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
| Security verified findings | High | Platform security | fix | 2026-06-09 | No verified findings remain open in `security-report/verified-findings.md`. VF-001 fixed with `tests/test_sql_agent_security.py`; VF-002 closed by owner rotation attestation plus tracked secret scan; VF-004 fixed with `tests/test_iac_secret_defaults.py`; VF-005 fixed with `tests/test_sandbox.py`. |
| VF-002 OpenAI key remediation | High | Platform operations | fix | 2026-06-09 | Repo-root `.env` is the single ignored local environment file with owner-provided rotated OpenAI project key; app-level env files removed; Vite/backend config read root `.env`; `.env` is untracked; masked key shape validation passed; `tools/secret_hygiene_scan.py` clean for tracked files. Provider liveness check was attempted but local runtime returned `URLError`, so no provider availability claim is made. |
| RuntimeEngine default promotion deferred | Medium | Platform architecture | defer | 2026-06-04 | `docs/m22-lifecycle-parity-matrix.md`; parity harness exists but default promotion remains deferred |
| Deep DS/ML visual observability expansion remains open | Medium | Product / Platform | defer | 2026-06-09 | `docs/product-strategy-agentic-dsml-platform.md`, `tasks.md`; implemented trace metadata/previews, Run Matrix, Reports lineage/output board, persisted ModelOps registry/monitor/deployment store, and retrain candidates. Remaining expansion: richer graph visualization, rebuild-impact lineage workflows, model monitor jobs/alerts, and deployment automation beyond metadata handoff. |
| Control Plane live/external expansion remains open | Medium | Platform / Frontend | defer | 2026-06-09 | `platform_api/control_plane/`, `tests/test_control_plane.py`, `tasks.md`, `docs/universal-platform-control-plane.md`; local CLI and stdio bridge adapters exist. Live external Prefect connectivity and LLM-assisted planner remain planned. |
