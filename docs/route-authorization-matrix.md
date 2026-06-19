# Route Authorization Matrix

Status: active security audit note for design-partner release.

Last updated: 2026-06-04.

## Scope

This matrix records the expected authorization dependency for platform API
routes that handle tenant, workspace, admin, artifact, workflow, run, or data
source state. Public operational endpoints are listed separately.

## Public or Session Routes

| Surface | Expected dependency | Notes |
|---|---|---|
| `/healthz`, `/health`, `/ready`, `/metrics` | none | Public operational probes; `/ready` validates database availability. |
| `/v1/auth/*` | auth route policy | CSRF/dev-login/OIDC behavior is owned by auth tests and release-profile policy. |
| `/v1/me` | `get_principal` plus workspace/tenant lookup | Returns caller context only. |
| `/v1/errors` | structured frontend error intake | Does not expose tenant data. |

## Workspace-Scoped Member Routes

| Surface | Expected dependency | Evidence |
|---|---|---|
| `/v1/data-sources/*` | `require_workspace_member` | Data source service tests and SQL Server secret tests. |
| `/v1/artifacts/*` | `require_workspace_member` or explicit principal plus service workspace lookup | `test_artifact_service.py`, `test_artifact_redirect_allowlist.py`. |
| `/v1/chat/*` | explicit principal plus workspace/session service checks | `test_chat_service.py`, `test_chat_and_signals.py`, `test_security_injection.py`. |
| `/v1/control-plane/catalog`, `/v1/control-plane/query`, `/v1/control-plane/actions/plan` | explicit principal plus control-plane policy checks | `test_control_plane.py`; catalog descriptors enforce required role and field redaction. |
| `/v1/discovery/*` | `require_workspace_member` | Discovery route dependency scan. |
| `/v1/runs/*` | `require_workspace_member` or explicit principal plus run workspace checks | Run service, agent trace, and signal route tests. |
| `/v1/scheduler` read endpoints | `require_workspace_member` | Scheduler tests cover member-readable surfaces. |
| `/v1/strategy/*` | `require_workspace_member` | Strategy route dependency scan. |
| `/v1/workflow-node-types/*` | `require_workspace_member` | Node catalog is workspace-contextual. |
| `/v1/workflows` read/create/detail surfaces | `require_workspace_member` | Workflow service and lifecycle tests. |
| `/v1/versioning/{deployment}/current` | `require_workspace_member` | Versioning route dependency scan. |

## Workspace Admin Routes

| Surface | Expected dependency | Evidence |
|---|---|---|
| `/v1/workflows/{id}/publish` | `require_workspace_admin` | Workflow lifecycle and M6 endpoint tests. |
| `/v1/workflows/{id}/archive` | `require_workspace_admin` | Workflow lifecycle and M6 endpoint tests. |
| `/v1/workflows/{id}/versions/*` mutating surfaces | `require_workspace_admin` | Workflow/versioning tests. |
| `/v1/scheduler` mutating surfaces | `require_workspace_admin` | Scheduler tests. |
| `/v1/hitl/{id}/approve`, `/v1/hitl/{id}/reject` | workspace admin check after membership lookup | HITL route tests. |
| `/v1/versioning/*` mutating surfaces | `require_workspace_admin` | Versioning tests. |
| `/v1/control-plane/actions/execute` workspace actions | explicit principal plus control-plane execution policy | `test_control_plane.py`; execution re-checks RBAC and writes audit evidence. |

## Tenant Admin Routes

| Surface | Expected dependency | Evidence |
|---|---|---|
| `/v1/admin/*` | `require_tenant_admin` | `test_admin_contract.py` route dependency guard. |
| `/v1/admin/runtime-engine/parity` | `require_tenant_admin` | `test_admin_contract.py`; read-only RuntimeEngine parity evidence endpoint. |
| `/v1/control-plane/actions/execute` admin actions | control-plane execution policy requiring tenant admin | `test_control_plane.py`; DLQ replay is high-risk and requires confirmation. |
| `/v1/finops/*` | `require_tenant_admin` | `test_admin_contract.py` route dependency guard. |
| `/v1/provisioning/*` tenant admin actions | tenant admin service checks | `test_provisioning_service.py`, `test_provisioning_routes.py`. |

## Current Evidence Commands

```powershell
cd apps/platform-api-app
python -m pytest tests/test_admin_contract.py tests/test_rbac_policy.py tests/test_tenant_isolation_hardening.py tests/test_provisioning_service.py tests/test_provisioning_routes.py -q
python -m pytest tests/test_artifact_service.py tests/test_artifact_redirect_allowlist.py tests/test_chat_service.py tests/test_chat_and_signals.py tests/test_security_injection.py -q
python -m pytest tests/test_control_plane.py -q
python -m pytest tests/test_workflow_ir_v2.py::test_worker_records_safe_agent_execution_trace tests/test_workflow_ir_v2.py::test_worker_records_failed_agent_trace_without_secret_leak -q
```

## Notes

- Cross-workspace object reads should return `404` where possible to avoid
  leaking object existence.
- Mutating workspace routes should require workspace admin/owner unless the
  action is explicitly member-safe.
- Tenant-level admin and FinOps routes must not be added without the
  `require_tenant_admin` dependency guard.
