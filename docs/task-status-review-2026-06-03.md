# Task Status Review - 2026-06-03

## Scope

Reviewed the active backlog in `tasks.md` against the current working tree and reran the release-relevant gates that can run locally without a long-lived app stack.

## Current Git State

The repo is attached to `origin/main`, but the working tree remains intentionally dirty while this review applies fixes and records evidence. Runtime/generated folders such as `frontend/playwright-report/`, `frontend/test-results/`, `graphify-out/`, `outputs/`, and local DB/log files still need push hygiene before staging.

## Evidence Captured

| Gate | Result | Notes |
|------|--------|-------|
| Frontend typecheck | Passed | `npm.cmd run typecheck` |
| Frontend lint | Passed with warnings | 2026-06-04 `npm.cmd run lint`; 0 errors, 14 warnings remain |
| Frontend unit tests | Passed | 2026-06-04 `npm.cmd run test`; 37 files / 243 tests passed |
| Frontend build | Passed with chunk warning | `npm.cmd run build`; bundle warning only |
| Platform API tests | Passed | 2026-06-04 `rtk pytest -q`; 717 passed |
| Root Python tests | Passed | 2026-06-04 `python -m pytest tests -q`; 99 passed |
| Selected agent/plugin tests | Passed | 353 passed with `--basetemp .tmp-tests/plugin-basetemp` |
| Migration check | Passed | 2026-06-09 SQLite temp DB `alembic upgrade head` through `0021_modelops_production_store` |
| Playwright golden path | Passed | `npm.cmd run test:e2e -- --reporter=line`; 24/24 passed after rate-limit-safe fixture strategy and route-selector hardening. |
| Local HTTP smoke | Passed | `GET /healthz`, `/ready`, `/metrics`, frontend root, Vite proxy dev login, and proxy `/v1/me` returned expected 200 responses. |
| Universal Platform Control Plane targeted backend | Passed | 2026-06-04 `python -m pytest tests/test_control_plane.py tests/test_chat_service.py tests/test_runs_contract.py -q`; 39 passed. |
| Universal Platform Control Plane targeted frontend | Passed | 2026-06-04 `npm.cmd run test -- src/app/api/controlPlane.test.ts src/app/api/workflows.test.ts src/app/components/chat/ArtifactCard.test.tsx src/app/screens/Workflows.test.tsx src/app/screens/WorkflowDetail.test.tsx`; 5 files / 27 tests passed. |
| RuntimeEngine parity harness | Passed | 2026-06-04 `python -m pytest tests/test_runtime_engine_parity_service.py tests/test_admin_contract.py::test_runtime_engine_parity_report_is_tenant_admin_readable tests/test_admin_contract.py::test_admin_and_finops_routes_require_tenant_admin -q`; 3 passed. |
| Workflow Run Matrix targeted frontend | Passed | 2026-06-04 `npm.cmd run test -- src/app/screens/RunsList.test.tsx src/app/api/runs.test.ts`; 2 files / 14 tests passed. |
| Artifact Lineage / Output Board targeted | Passed | 2026-06-04 `pytest apps/platform-api-app/tests/test_artifact_service.py apps/platform-api-app/tests/test_artifacts_routes.py -q`; 18 passed. `npm.cmd run test -- src/app/screens/Reports.test.tsx`; 3 passed. |
| Agent Cockpit / Trace Inspector enrichment | Passed | 2026-06-04 `npm.cmd run test -- src/app/screens/Agents.test.tsx src/app/screens/RunDetail.test.tsx`; 2 files / 14 tests passed. |
| Agent trace metadata and ModelOps first-pass | Passed | 2026-06-04 backend targeted set passed 23 / skipped 1; frontend targeted set passed 3 files / 15 tests; typecheck passed; lint passed with 14 existing warnings; migration check passed through `0020_agent_trace_metadata`. |
| ModelOps production store and Control Plane adapters | Passed | 2026-06-09 `python -m pytest -q apps/platform-api-app/tests/test_modelops.py apps/platform-api-app/tests/test_control_plane.py`; 14 passed. `python -m py_compile tools/platform_control_plane_cli.py tools/platform_control_plane_mcp_adapter.py`; passed. SQLite migration check passed through `0021_modelops_production_store`. |
| Secret hygiene local scan | Passed | 2026-06-09 repo-root `.env` exists as the single ignored local env file with owner-provided rotated OpenAI project key; app-level env files removed; tracked env files absent; masked key shape validation passed; tracked secret scan clean. |
| Frontend typecheck after control-plane work | Passed | 2026-06-04 `npm.cmd run typecheck`. |
| Frontend lint after control-plane work | Passed with warnings | 2026-06-04 `npm.cmd run lint`; 0 errors, 14 warnings. |

## Fixes Applied During Review

- Fixed ESLint typed-rule configuration, ignored Playwright generated output folders, and updated login e2e helpers for the current collapsed developer-token UI.
- Fixed promise catch callback typing and an empty catch block.
- Made OIDC missing JWKS return `503` instead of `500`.
- Updated stale workflow tests to use a known agent alias instead of `tool: test`.
- Made real LLM workflow executor test skip cleanly on OpenAI quota exhaustion.
- Preserved consumed workflow signals in `SignalStore.list_all()` until explicit cleanup.
- Restored numeric CloudOps monthly cost artifact while retaining decimal string detail.
- Made dynamic workflow resolution produce a deterministic fallback spec when the LLM is unavailable or returns invalid output.
- Fixed `SQLConnector` SQLite engine creation by not passing TCP pool timeout arguments to SQLite.
- Added SQL Server structured data source support: frontend fielded form, backend credential-safe response contract, durable encrypted secret store, masked metadata, and targeted backend/frontend tests.
- Added Settings configuration-center scope for Workspace+User+Admin categories with read-only/not-configured states for unsupported persistence.
- Converted `security-report/verified-findings.md` to per-finding triage fields with decision, owner, target date, status, and required evidence.
- Added route/API contract summary in `docs/route-api-contract-summary.md`.
- Added release notes template in `docs/release-notes-template.md`.
- Closed upload, artifact access, and chart/report safe-render checks with targeted backend and frontend regression tests.
- Added route authorization matrix and closed tenant/workspace/admin route gate checks with RBAC and admin dependency tests.
- Closed workflow designer lifecycle and natural-language schedule parsing with frontend scheduler tests and backend parser tests.
- Added release dependency lock policy in `docs/release-dependency-lock-policy.md`.
- Added changed-surface security check report in `security-report/changed-surface-check-2026-06-03.md`.
- Closed release-profile fallback review; `/runs/{id}/logs` now rejects mock fallback in release profile.
- Generated maintainability snapshot `tools/maintainability_2026-06-03_after_plan.json`.
- Added conservative dead-code dynamic surface triage in `docs/dead-code-dynamic-surface-triage.md`.
- Fixed rate-limit bucket isolation so `/v1/me` traffic no longer consumes the stricter `/v1/auth/login/dev` allowance, added a middleware regression test, and made Playwright e2e auth rate-limit-safe with per-test headers plus direct local dev cookie setup for non-login specs.
- Added stable UI test targets for visible upload drop zone, logout action, workflow designer canvas, and YAML editor.
- Added M22 lifecycle parity matrix and kept `staged_m22` out of the default production path until RuntimeEngine lifecycle evidence is reviewed.
- Added product strategy planning for the next implementation wave: agentic DS/ML operations positioning, visual agent/workflow observability, ModelOps lifecycle, artifact lineage, run matrix, and chat control-plane direction.
- Added independent Universal Platform Control Plane foundation under `platform_api/control_plane/`: catalog descriptors, policy/redaction, query DTOs, resolver registry, provenance, action plan/execute flow, and `/v1/control-plane/*` routes.
- Added `docs/universal-platform-control-plane.md` as the durable architecture note for control-plane boundaries, APIs, guardrails, evidence, and open expansion items.
- Integrated platform chat routing so platform-state questions return `platform_query_result` artifacts without calling the DS/ML agent registry or ChatWorkspace analytical routing path.
- Added frontend Control Plane API client and generic `platform_query_result` renderer with tables, metrics, provenance/redaction notes, canonical links, and action confirmation support.
- Expanded Control Plane DB-backed coverage with workflow spec schedule metadata, tenant-admin FinOps summary, artifact-backed ModelOps inventory, release docs task counts, and artifact lineage relationship payloads.
- Added frontend relationship rendering for `platform_query_result` sections.
- Added first-pass Agent Cockpit execution summary on the Agents screen by querying Control Plane `run.nodes` and grouping executions, failures, and retries by node type.
- Added safe agent execution trace storage: `agent_execution_traces`, worker start/complete trace writes, `/v1/runs/{run_id}/agent-traces`, Control Plane `agent.traces`, and frontend typed API client.
- Added first-pass Agent Run Detail surface as a Run Detail `Agent Traces` tab backed by safe trace summaries.
- Extended Agent Cockpit with `run.nodes` + `agent.traces` metrics for success rate, tool calls, artifact counts, average trace duration, node-type artifact/duration detail, and top failure signals; extended Run Detail with a selected Trace Inspector for safe input/output summaries, tool calls, artifact IDs, timings, executor, and errors.
- Fixed Workflow Designer new-route mismatch by routing New Workflow to the declared `/workflows/new` path.
- Replaced Workflow Detail mock YAML/version-history constants with real workflow spec serialization and version-history API loading; restore/diff remain explicitly disabled until backend contracts exist.
- Added deterministic RuntimeEngine parity harness and tenant-admin `/v1/admin/runtime-engine/parity` endpoint that maps logs, signals, artifacts, retry, cancel, and scheduler non-replacement status to current platform contracts without changing `/v1/runs` default behavior.
- Added VF-005 sandbox runner regression coverage with `tests/test_sandbox.py`; trivial dataframe execution and blocked import tests passed, and root Python suite now passes 99 tests.
- Fixed VF-001 SQL-agent RCE path by removing generated-Python `exec` from live SQL connection execution; `tests/test_sql_agent_security.py` passed and root Python suite now passes 99 tests.
- Fixed VF-004 weak DB defaults by making Helm password fields fail-closed and requiring docker compose `POSTGRES_PASSWORD`; IaC/Helm targeted set passed 127 tests and Platform API suite passed 717 tests.
- Added first-pass Workflow Run Matrix / Heatmap to RunsList using run node execution data for the recent filtered run set.
- Added first-pass Reports Artifact Lineage / Output Board; artifact list responses now expose safe workspace/tenant/node/parent lineage metadata and honor `kind` / `workflow_run_id` filters.
- Added nullable safe agent trace metadata fields for token usage, cost summary, evaluation summary, and version metadata; Run Detail now renders these plus artifact previews, and Agent Cockpit shows capture counts.
- Added artifact-backed ModelOps first-pass surface with `/v1/modelops/summary`, `/modelops`, Control Plane `modelops` resolver integration, monitor snapshots, drift/performance status, and retrain candidates.
- Expanded release docs resolver with deterministic document snippet search and added `control_plane.adapters` descriptor/resolver for product chat, future CLI, and future MCP dependency direction.
- Added persisted ModelOps production store with `model_registry_entries`, `model_monitor_snapshots`, and `model_deployment_records`; added admin-only `/v1/modelops/registry`, `/monitors`, and `/deployments`; summary now merges persisted production state with artifact-backed fallback candidates.
- Added tenant-admin Control Plane FinOps trace cost/token aggregation from safe agent trace metadata.
- Added local `tools/platform_control_plane_cli.py` and dependency-light `tools/platform_control_plane_mcp_adapter.py` so CLI/MCP-style access uses the same Control Plane API instead of the DS/ML agent registry.
- Closed release checklist placeholder fields with role-based owner placeholders, local monitoring endpoints, CI workflow references, rollback trigger/procedure, and post-rollback verification steps.
- Accepted VF-003 GitHub Actions tag pinning risk for local/design-partner scope, fixed rollout `monitor` job dependency, and quoted Slack webhook shell arguments; SHA pinning remains a GA hardening follow-up.
- Added `tools/secret_hygiene_scan.py` for tracked OpenAI-style secret scans and recorded VF-002 local remediation status.
- Standardized local env handling to a single repo-root `.env`; frontend Vite config and backend settings now read that root file, and app-level env files were removed.

## Still Open

- Future M22 default promotion remains deferred for review; the endpoint/parity harness now exists, but the current release keeps Prefect-backed `/v1/runs` canonical.
- Named release owner, incident channel, and production dashboard URLs still need real assignment before GA; role placeholders and local endpoints are now filled so the checklist is executable for local/design-partner scope.
- Security finding VF-002 is closed by owner rotation attestation plus repo hygiene evidence; provider liveness check was attempted but local runtime returned `URLError`, so availability is not claimed. VF-003 is accepted risk for local/design-partner scope and remains GA hardening.
- SQL Server data source flow is closed for local design-partner scope with mocked connector smoke; production deployment still requires a real `DATA_SOURCE_SECRET_KEY` and environment-owned SQL Server credentials.
- Settings configuration center still needs product review and API-backed persistence for categories that are currently read-only.
- Product strategy is now documented, the Universal Platform Control Plane foundation is implemented, Agent Cockpit has trace-backed execution/cost-token capture metrics, safe agent trace storage exists, Run Detail has a selected Trace Inspector with artifact previews, RunsList has a first-pass Workflow Run Matrix, Reports has a first-pass Artifact Lineage / Output Board, and ModelOps has persisted registry/monitor/deployment metadata plus artifact-backed fallback candidates. Remaining product expansion: rebuild-impact lineage workflows, artifact bundle exploration, monitor jobs/alerts, deployment automation beyond metadata handoff, and richer graph visualization.
- Control Plane live/external expansion now includes release docs search, local CLI adapter, local stdio bridge adapter, persisted ModelOps, and trace cost/token FinOps summary; live external Prefect connectivity and LLM-assisted planner depth remain future expansion.
