# Changed Surface Security Check - 2026-06-03

Status: completed for the 2026-06-03 pass; updated with 2026-06-04 Control Plane changed surface evidence.

## Changed Surfaces

| Surface | Change | Security concern | Evidence |
|---|---|---|---|
| SQL Server data sources | Structured form, safe response, durable secret store | Credential leakage, non-durable secrets, cross-workspace secret access | `tests/test_data_sources_sql_server.py` |
| Data source API | Optional URI for SQL Server, safe metadata | Password or `secret_ref` returned to frontend | `tests/test_data_sources_sql_server.py`, `tests/test_data_source_service.py` |
| Upload handling | Revalidated upload security task | Path traversal, MIME mismatch, malware mode, oversized/unsafe files | `tests/test_chat_service.py`, `tests/test_chat_and_signals.py`, `tests/test_security_injection.py`, `tests/test_malware_scan.py` |
| Artifact access/rendering | Revalidated backend authorization and frontend safe render | Cross-workspace artifact access, unsafe redirects, XSS in report/table artifacts | `tests/test_artifact_service.py`, `tests/test_artifact_redirect_allowlist.py`, `frontend/src/app/components/chat/ArtifactCard.test.tsx` |
| Admin/FinOps routes | Added dependency guard test | Privileged endpoints missing tenant-admin dependency | `tests/test_admin_contract.py`, `tests/test_rbac_policy.py`, `tests/test_tenant_isolation_hardening.py` |
| Universal Platform Control Plane | Catalog-backed platform query/action layer, chat integration, FinOps, docs search, artifact-backed ModelOps, adapter metadata, lineage relationships | Unauthorized platform-state reads, field-level secret leakage, mutating action without confirmation/audit, accidental DS/ML agent registry dependency, tenant-admin FinOps exposure, unsafe artifact URI display | `tests/test_control_plane.py`, `frontend/src/app/api/controlPlane.test.ts`, `frontend/src/app/components/chat/ArtifactCard.test.tsx` |
| Agent execution traces | Safe trace storage, run trace endpoint, Control Plane `agent.traces`, frontend typed client | Raw private reasoning or secret leakage, cross-workspace trace reads, unsafe error propagation | `tests/test_workflow_ir_v2.py`, `tests/test_control_plane.py`, `frontend/src/app/api/runs.test.ts` |
| RuntimeEngine parity endpoint | Tenant-admin `/v1/admin/runtime-engine/parity` read-only harness | Privileged runtime evidence exposed without admin guard, accidental default promotion, unsafe lifecycle metadata leakage | `tests/test_runtime_engine_parity_service.py`, `tests/test_admin_contract.py` |
| Sandbox runner reliability | VF-005 regression coverage for sandbox subprocess execution | Sandbox control failure returning to runtime, blocked import bypass regression | `tests/test_sandbox.py` |
| SQL-agent execution | Removed generated-Python `exec` from SQL-agent live connection path | RCE/capability escape through generated code with access to SQL connection, pandas, SQLAlchemy, or filesystem | `tests/test_sql_agent_security.py` |
| IaC database secrets | Helm and docker compose no longer ship weak DB password defaults | Default credential reuse in deployment templates | `tests/test_iac_secret_defaults.py`, `tests/test_m15_helm.py`, `tests/test_m15_helm_rendering.py` |

## Commands

```powershell
cd apps/platform-api-app
python -m pytest tests/test_data_source_service.py tests/test_data_sources_sql_server.py -q
python -m pytest tests/test_chat_service.py tests/test_chat_and_signals.py tests/test_security_injection.py tests/test_artifact_service.py tests/test_artifact_redirect_allowlist.py tests/test_malware_scan.py -q
python -m pytest tests/test_admin_contract.py tests/test_rbac_policy.py tests/test_tenant_isolation_hardening.py tests/test_provisioning_service.py tests/test_provisioning_routes.py -q
python -m pytest tests/test_control_plane.py tests/test_chat_service.py tests/test_runs_contract.py -q
python -m pytest tests/test_control_plane.py tests/test_runs_contract.py tests/test_workflow_ir_v2.py::test_worker_records_safe_agent_execution_trace tests/test_workflow_ir_v2.py::test_worker_records_failed_agent_trace_without_secret_leak -q
python -m pytest tests/test_runtime_engine_parity_service.py tests/test_admin_contract.py::test_runtime_engine_parity_report_is_tenant_admin_readable tests/test_admin_contract.py::test_admin_and_finops_routes_require_tenant_admin -q
python -m pytest tests/test_iac_secret_defaults.py tests/test_m15_helm.py tests/test_m15_helm_rendering.py -q
```

```powershell
cd ..\..
python -m pytest tests/test_sandbox.py -q
python -m pytest tests/test_sql_agent_security.py -q
python -m pytest tests -q
```

```powershell
cd frontend
npm.cmd run test -- src/app/components/chat/ArtifactCard.test.tsx src/app/screens/Reports.test.tsx
npm.cmd run test -- src/app/api/controlPlane.test.ts src/app/api/workflows.test.ts src/app/components/chat/ArtifactCard.test.tsx src/app/screens/Workflows.test.tsx src/app/screens/WorkflowDetail.test.tsx
npm.cmd run test -- src/app/api/runs.test.ts
```

## Results

- Data source service and SQL Server tests: 22 passed.
- Upload/artifact/security backend tests: 65 passed.
- Admin/RBAC/provisioning tests: 49 passed.
- Frontend artifact/report safe-render tests: 9 passed.
- Control Plane backend targeted tests: 39 passed on 2026-06-04.
- Control Plane frontend targeted tests: 5 files / 27 tests passed on 2026-06-04.
- Agent trace targeted backend/control-plane set: 17 passed on 2026-06-04.
- Agent trace frontend API test: 7 passed on 2026-06-04.
- RuntimeEngine parity endpoint targeted backend tests: 3 passed on 2026-06-04.
- Sandbox runner regression tests: 2 passed on 2026-06-04.
- SQL-agent RCE regression tests: 3 passed on 2026-06-04.
- Root Python suite after security regression coverage: 99 passed on 2026-06-04.
- IaC secret/Helm regression tests: 127 passed on 2026-06-04.
- Full Platform API suite: 717 passed on 2026-06-04.
- Full frontend suite: 37 files / 243 tests passed on 2026-06-04.

## Residual Risk

- `security-report/verified-findings.md` now contains no open verified findings. VF-002 is closed by owner rotation attestation plus repo hygiene evidence; VF-003 is accepted risk for local/design-partner scope and remains GA hardening.
- This check validates changed surfaces from the current pass; it is not a full
  external penetration test or full static-analysis security scan.
