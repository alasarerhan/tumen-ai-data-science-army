# Changed Surface Security Check - 2026-06-03

Status: completed for this implementation pass.

## Changed Surfaces

| Surface | Change | Security concern | Evidence |
|---|---|---|---|
| SQL Server data sources | Structured form, safe response, durable secret store | Credential leakage, non-durable secrets, cross-workspace secret access | `tests/test_data_sources_sql_server.py` |
| Data source API | Optional URI for SQL Server, safe metadata | Password or `secret_ref` returned to frontend | `tests/test_data_sources_sql_server.py`, `tests/test_data_source_service.py` |
| Upload handling | Revalidated upload security task | Path traversal, MIME mismatch, malware mode, oversized/unsafe files | `tests/test_chat_service.py`, `tests/test_chat_and_signals.py`, `tests/test_security_injection.py`, `tests/test_malware_scan.py` |
| Artifact access/rendering | Revalidated backend authorization and frontend safe render | Cross-workspace artifact access, unsafe redirects, XSS in report/table artifacts | `tests/test_artifact_service.py`, `tests/test_artifact_redirect_allowlist.py`, `frontend/src/app/components/chat/ArtifactCard.test.tsx` |
| Admin/FinOps routes | Added dependency guard test | Privileged endpoints missing tenant-admin dependency | `tests/test_admin_contract.py`, `tests/test_rbac_policy.py`, `tests/test_tenant_isolation_hardening.py` |

## Commands

```powershell
cd apps/platform-api-app
python -m pytest tests/test_data_source_service.py tests/test_data_sources_sql_server.py -q
python -m pytest tests/test_chat_service.py tests/test_chat_and_signals.py tests/test_security_injection.py tests/test_artifact_service.py tests/test_artifact_redirect_allowlist.py tests/test_malware_scan.py -q
python -m pytest tests/test_admin_contract.py tests/test_rbac_policy.py tests/test_tenant_isolation_hardening.py tests/test_provisioning_service.py tests/test_provisioning_routes.py -q
```

```powershell
cd frontend
npm.cmd run test -- src/app/components/chat/ArtifactCard.test.tsx src/app/screens/Reports.test.tsx
```

## Results

- Data source service and SQL Server tests: 22 passed.
- Upload/artifact/security backend tests: 65 passed.
- Admin/RBAC/provisioning tests: 49 passed.
- Frontend artifact/report safe-render tests: 9 passed.

## Residual Risk

- `security-report/verified-findings.md` still contains findings that require
  separate fix/regression work.
- This check validates changed surfaces from the current pass; it is not a full
  external penetration test or full static-analysis security scan.
