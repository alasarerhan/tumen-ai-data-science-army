# Universal Platform Control Plane

Status: foundation plus DB-backed coverage expansion implemented on 2026-06-04; live/external coverage remains open.

## Purpose

The Universal Platform Control Plane is the deterministic platform-query and
governed-action layer behind product chat. It is independent from the DS/ML
agent registry, workflow agent planners, and analytical ChatWorkspace routing.

LLMs may help translate language into a query plan or summarize results, but
the source of truth is platform state: database rows, services, route
contracts, configuration, operational status, artifacts, signals, audit logs,
and documented release metadata.

## Backend Boundary

Path: `apps/platform-api-app/platform_api/control_plane/`

Modules:

- `catalog.py`: resource descriptors and explicit non-queryable surfaces.
- `schemas.py`: query, action, provenance, relationship, and result DTOs.
- `policies.py`: role checks and field-level redaction.
- `query.py`: planner, resolver registry, result composition, and chat helper.
- `actions.py`: governed action planning and execution.

Route:

- `GET /v1/control-plane/catalog`
- `POST /v1/control-plane/query`
- `POST /v1/control-plane/actions/plan`
- `POST /v1/control-plane/actions/execute`

## Initial Catalog Coverage

- Identity: current user, tenant, workspace, membership context.
- Configuration: settings categories, auth mode, data source policy, secret
  policy, scheduler visibility.
- Data sources: CSV/Excel/local, generic SQL, SQL Server safe metadata and
  test status.
- Chat uploads: safe upload metadata.
- Workflows: workflow specs, lifecycle state, versions, timestamps, canonical
  links.
- Schedules: workflow spec schedule metadata; live Prefect deployment state
  adapter remains open.
- Runs: run state, retry/resume/cancel status, node executions, signals.
- Artifacts: safe artifact metadata and lineage relationship payloads.
- Governance: HITL approvals and audit events.
- Admin/Ops: health/readiness/metrics-oriented summaries, queue/DLQ/admin
  state.
- Release docs: active release checklist, task status, route/API contract, and
  product strategy references.
- FinOps: tenant-admin storage/run/upload summary and cleanup recommendations.
- Agents and ModelOps: Agents screen now has trace-backed cockpit metrics
  from `run.nodes` and `agent.traces`; safe `agent_execution_traces`
  storage/read contracts, Control Plane `agent.traces`, and Run Detail Trace
  Inspector are implemented. Cost/token metadata, evaluation metadata,
  rendered artifact previews, and span timelines remain future work. ModelOps now
  exposes artifact-backed model/metrics inventory while registry,
  deployment, monitoring, drift, and retraining state remain open.

## Query Contract

Every `platform_query_result` must carry:

- Summary.
- Sections containing entity cards, tables, metrics, timelines, links, or
  relationship payloads.
- Provenance with resource key, resolver, timestamp, filters, and redaction
  evidence.
- Redaction/freshness notes where relevant.

The planner may only emit plans against catalog resources. A platform surface
that is not in the catalog is not considered chat-queryable.

## Action Contract

Mutating actions are separate from read queries:

- Plan first.
- Determine risk and whether confirmation is required.
- Execute only with RBAC re-check.
- Write audit evidence for every executed action.

Initial exposed actions:

- Workflow publish/archive/trigger.
- Run cancel/retry/resume.
- Node retry.
- Signal emit.
- Schedule pause/resume.
- Tenant-admin DLQ replay with high-risk confirmation.

Not exposed in the first wave:

- Secret rotation.
- Destructive workspace deletion.
- Raw secret reads.
- Private agent reasoning.

## Frontend Contract

Path: `frontend/src/app/api/controlPlane.ts`

Renderer: `frontend/src/app/components/chat/ArtifactCard.tsx`

AI Workspace renders Control Plane responses as `platform_query_result`
artifacts and routes action confirmation through the execute endpoint only
after explicit user confirmation.

The Agents screen also consumes Control Plane `run.nodes` and `agent.traces`
output for the Agent Cockpit execution summary, tool-call/artifact metrics, and
failure signals, including cost/token/evaluation/version capture counts. Run
Detail consumes `/v1/runs/{run_id}/agent-traces` for the Agent Traces tab,
selected Trace Inspector, safe metadata blocks, and artifact previews. Future
dedicated Agent Run Detail surfaces should continue to consume safe trace
contracts and Control Plane `agent.traces` rather than reading raw worker
internals.

ModelOps coverage combines artifact-backed candidates with persisted production
metadata: `/v1/modelops/summary`, `/v1/modelops/registry`, `/monitors`,
`/deployments`, and Control Plane `modelops` expose registry entries, monitor
snapshots, deployment metadata, drift/performance status, and retrain
candidates. Monitor jobs, alert routing, deployment automation, and live serving
health checks remain future production work.

## Test Evidence

Backend:

```powershell
cd apps/platform-api-app
python -m pytest tests/test_control_plane.py tests/test_chat_service.py tests/test_runs_contract.py -q
```

Result on 2026-06-04: 39 passed.

Frontend:

```powershell
cd frontend
npm.cmd run test -- src/app/api/controlPlane.test.ts src/app/api/workflows.test.ts src/app/components/chat/ArtifactCard.test.tsx src/app/screens/Workflows.test.tsx src/app/screens/WorkflowDetail.test.tsx
npm.cmd run test -- src/app/screens/Agents.test.tsx
npm.cmd run test -- src/app/screens/RunDetail.test.tsx src/app/hooks/useRuns.test.tsx src/app/api/runs.test.ts
npm.cmd run test -- src/app/api/runs.test.ts
npm.cmd run typecheck
```

Result on 2026-06-04: targeted Vitest passed 5 files / 27 tests; typecheck
passed. Agent Cockpit targeted test passed 5 tests, Run Detail trace targeted
set passed 3 files / 23 tests, run API trace endpoint test passed 7 tests,
Reports Artifact Lineage / Output Board targeted test passed 3 tests, Agent
Cockpit / Trace Inspector targeted tests passed 2 files / 14 tests, and the
full frontend suite passed 37 files / 243 tests after the latest cockpit
enrichment.

## Open Expansion

- Model monitor jobs, alert routing, deployment automation, and health checks
  beyond the persisted ModelOps metadata store.
- Provider-grade billing exports, cache, and storage-byte detail beyond
  tenant-admin trace cost/token FinOps summary.
- Live external Prefect deployment adapter beyond persisted workflow spec
  schedule metadata and workspace-scoped scheduler jobs.
- Richer relationship and lineage graph visualization beyond the first-pass Reports lineage board.
- Release/task/docs search beyond deterministic snippet matching.
- LLM-assisted planner constrained to the catalog.
- Hardened external MCP packaging beyond the local stdio bridge; adapter
  dependency direction and local script paths are cataloged in `control_plane.adapters`.
