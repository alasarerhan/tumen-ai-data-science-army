# Route and API Contract Summary

Status: active contract reference for the design-partner release.

Last updated: 2026-06-09.

## Ownership

| Surface | Backend owner | Frontend owner | Notes |
|---|---|---|---|
| Auth and session | Platform API | Frontend shell | Browser auth uses cookie/CSRF in release profile; local dev token path is for local verification only. |
| Workspaces and members | Platform API | Settings, shell | Workspace-scoped routes must resolve membership through backend authz dependencies. |
| Data sources | Platform API | Data Sources, Settings | CSV/Excel/local file, generic SQL URI, SQL Server, and MCP plugin are supported source categories. |
| Chat and uploads | Platform API | AI Workspace | Upload and message APIs must preserve tenant/workspace context and safe artifact rendering. |
| Universal Platform Control Plane | Platform API | AI Workspace, local CLI/stdio adapters | Catalog-backed query/action surface for platform state; independent from DS/ML agent registry and analytical chat routing. |
| Workflows and runs | Platform API | Workflow Designer, Runs, Pipeline Monitor | Workflow spec, publish, schedule, run, signals, logs, and HITL surfaces are linked release gates. |
| Admin and operations | Platform API | Admin Dashboard, Settings Operations | Scheduler, DLQ, cleanup, health, readiness, and metrics require role and observability evidence. |

## Auth and Session

| Method | Path | Request | Response | Contract notes |
|---|---|---|---|---|
| GET | `/v1/me` | Cookie or dev-token authenticated request | Current user, tenant, workspace, role context | Frontend treats missing/expired session as unauthenticated. |
| GET | `/v1/auth/csrf` | Browser request | CSRF token payload/cookie | Required before cookie-authenticated mutating requests when CSRF is enabled. |
| POST | `/v1/auth/login/dev` | Local dev token payload | Session cookie and current context | Local-only verification path; release profile must reject unsafe dev auth. |

## Data Sources

| Method | Path | Request | Response | Contract notes |
|---|---|---|---|---|
| GET | `/v1/data-sources?workspace_id=...` | Workspace id query | `{ items: DataSource[] }` | Backend ignores cross-workspace access by resolving membership context. |
| POST | `/v1/data-sources` | `workspace_id`, `name`, `kind`, optional `connection_uri`, optional `metadata` | Safe `DataSource` | Passwords and `secret_ref` are never returned. |
| PUT | `/v1/data-sources/{id}` | Partial update body | Safe `DataSource` | SQL Server password updates create a new opaque secret reference. |
| DELETE | `/v1/data-sources/{id}?workspace_id=...` | Workspace id query | `204` | Delete is scoped by workspace. |
| POST | `/v1/data-sources/{id}/test` | `workspace_id` | `{ status, message, details?, checked_at? }` | Error messages must not include credentials. |

### SQL Server Request Shape

Minimum SQL Server create/update payload:

```json
{
  "workspace_id": "workspace-uuid",
  "name": "Finance SQL Server",
  "kind": "sql_server",
  "metadata": {
    "provider": "sql_server",
    "host": "sql.company.local",
    "port": 1433,
    "database": "finance",
    "username": "analyst",
    "password": "submitted-once",
    "encrypt": true,
    "trust_server_certificate": false,
    "driver": "pymssql"
  }
}
```

Safe response requirements:

- `connection_uri` is safe for display and never contains the password.
- `metadata.password` is never returned.
- `metadata.secret_ref` is never returned.
- `metadata.has_secret` is returned when a backend secret exists.
- Secret material is stored behind the backend `data_source_secrets` boundary.

## Chat, Uploads, and Artifacts

| Method | Path | Request | Response | Contract notes |
|---|---|---|---|---|
| POST | `/v1/chat/sessions` | Workspace-scoped session body | Session payload | Session ownership must stay tenant/workspace scoped. |
| POST | `/v1/chat/messages` | Message and optional attachments | Message/run initiation payload | Upload safety checks remain a release gate. |
| GET | `/v1/chat/sessions/{id}/events` | SSE subscription | Event stream | Reconnect/cancel behavior is covered by frontend tests. |
| GET | `/v1/artifacts/{id}` | Authenticated artifact request | Artifact stream or metadata | Artifact access must be backend-authorized. |

## Universal Platform Control Plane

Detailed architecture note: `docs/universal-platform-control-plane.md`.

| Method | Path | Request | Response | Contract notes |
|---|---|---|---|---|
| GET | `/v1/control-plane/catalog?workspace_id=...` | Workspace id query | `{ items: PlatformResourceDescriptor[] }` | Descriptor catalog is the source of truth for chat-queryable platform resources. New user-facing routes/models need a descriptor or explicit non-queryable decision. |
| POST | `/v1/control-plane/query` | `workspace_id`, natural-language `query`, optional filters/limit | `platform_query_result` | Query results must include provenance, freshness, and redaction notes. Planner may only target catalog resources. |
| POST | `/v1/control-plane/actions/plan` | `workspace_id`, natural-language query or explicit action plan fields | `PlatformActionPlan` | Mutating operations are planned separately from execution and include risk/confirmation metadata. |
| POST | `/v1/control-plane/actions/execute` | `workspace_id`, action key, target, params, confirmation token | `PlatformActionResult` | RBAC is checked again at execute time and every executed action writes audit evidence. |

Initial coverage:

- Identity, workspace/user context, settings/config visibility.
- Data sources, chat uploads, workflows, workflow spec schedule metadata, runs, run nodes, agent traces, run signals, artifacts, artifact lineage relationships, approvals, audit, admin/ops, tenant-admin FinOps summary, release docs/task counts.
- Agent traces are catalog-backed through safe `agent_execution_traces`; richer agent/version governance remains future work.
- ModelOps exposes `/v1/modelops/summary`, admin-only `/v1/modelops/registry`, `/monitors`, and `/deployments`, plus Control Plane `modelops` records for persisted registry/monitor/deployment metadata and artifact-backed fallback candidates. Production serving health automation, monitor jobs, and alert routing remain future work.

Non-goals for the current contract:

- Product chat does not depend on MCP, CLI, `ai_data_science_team/tool_registry.py`, DS/ML agent executors, or ChatWorkspace analytical routing.
- Raw secrets, private agent reasoning, destructive workspace deletion, and secret rotation are not chat-exposed actions.

## Workflows, Runs, and Signals

| Method | Path | Request | Response | Contract notes |
|---|---|---|---|---|
| GET/POST | `/v1/workflows` | Workflow list/create | Workflow spec payloads | Designer save and validation use this surface. |
| POST | `/v1/workflows/{id}/publish` | Publish request | Published workflow/version | Publish flow remains part of full smoke. |
| POST | `/v1/runs` | Trigger request | Run payload | Workflow/run golden path remains open. |
| GET | `/v1/runs/{id}` | Run id | Run detail with metadata | Run detail drives timeline and artifact views. |
| GET | `/v1/runs/{id}/agent-traces` | Run id + workspace id | Safe agent trace summaries | Returns input/output key summaries, tool-call keys, artifact IDs, status, timing, and redacted error summaries; never raw private reasoning or secrets. |
| GET | `/v1/runs/{id}/logs` | SSE/log query | Log stream or log list | Error and reconnect behavior must remain credential-safe. |
| GET | `/v1/runs/{id}/signals` | SSE/signal query | Signal stream | Signal history is retained until explicit cleanup. |

## Admin Runtime Evidence

| Method | Path | Request | Response | Contract notes |
|---|---|---|---|---|
| GET | `/v1/admin/runtime-engine/parity` | Tenant-admin request | RuntimeEngine parity report | Deterministic read-only harness; maps RuntimeEngine logs, signals, artifacts, retry, cancel, and scheduler non-replacement to current platform contract targets. Does not promote `staged_m22` as default. |

## Operations

| Method | Path | Request | Response | Contract notes |
|---|---|---|---|---|
| GET | `/healthz` | None | Health payload | Basic liveness smoke. |
| GET | `/ready` | None | Readiness payload | Must be verified before release sign-off. |
| GET | `/metrics` | None | Metrics text | Monitoring owner/dashboard fields remain release checklist gates. |
| GET/POST | `/v1/admin/*` | Admin role context | Admin operation payloads | Scheduler, DLQ, cleanup, and replay actions must be role-gated. |

## Compatibility Rules

- Existing generic SQL URI payloads remain valid.
- SQL Server fielded form uses `kind: "sql_server"` and does not require frontend-visible raw URI construction.
- Backend may add safe metadata fields, but must not expose passwords, encrypted payloads, or secret references.
- Frontend must render unsupported settings as read-only/not-configured until real backend persistence exists.
- Control Plane query/action resources must be catalog-backed, RBAC checked, redacted, and provenance-bearing.
