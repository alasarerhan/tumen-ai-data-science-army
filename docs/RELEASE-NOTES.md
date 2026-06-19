# Release Notes Template & Examples

> Canonical release notes template + filled example.
> Replaces `docs/release-notes-template.md` and `planning_docs/strategy_execution/release_notes_m20_draft.md`.

Use the template below for every design-partner, staging, GA candidate, or GA release.

---

## Template

### Release Metadata

- Release name:
- Release type: design-partner | staging | GA candidate | GA
- Release date:
- Commit SHA:
- Branch:
- Owner:
- Approver:
- Rollback owner:

### Summary

Briefly describe the user-visible change, target users, and release intent.

### Shipped Changes

- Product:
- Frontend:
- Backend/API:
- Data/model/migrations:
- Security:
- Operations:
- Documentation:

### Public API and Contract Changes

- Added endpoints:
- Changed endpoints:
- Deprecated endpoints:
- Compatibility notes:

### Security and Privacy Notes

- Auth/session impact:
- Tenant/workspace isolation impact:
- Secret handling impact:
- Upload/artifact safety impact:
- Accepted/deferred findings:

### Test Evidence

| Gate | Command or evidence | Result | Notes |
|---|---|---|---|
| Frontend typecheck | | | |
| Frontend lint | | | |
| Frontend unit tests | | | |
| Backend tests | | | |
| Migration check | | | |
| Playwright golden path | | | |
| Smoke test | | | |
| Security regression | | | |

### Known Issues and Open Gates

- (none / list)

### Rollback Plan

- Rollback trigger:
- Rollback command/procedure:
- Data rollback/migration note:
- Verification after rollback:

### Monitoring and Support

- Dashboard:
- Alerts:
- Logs:
- On-call/contact:
- Incident doc:

---

## Example: M20 Release Candidate (2026-03-23, v0.20.0-rc1)

### Release Metadata

- Release name: M20 Release Candidate
- Release type: design-partner / staging candidate
- Release date: 2026-03-23
- Commit SHA: (filled at release time)
- Branch: `main`
- Owner: Platform Release Owner
- Approver: Security + SRE + Product
- Rollback owner: Platform On-call

### Summary

First release candidate with full chat/session/upload/signal APIs, AI Workspace UI, Workflow Designer, and Pipeline Monitor. Local development profile is supported with SQLite; production deployment requires M8 Cloud Run hardening approval.

### Shipped Changes

- Product: AI Workspace (M21) conversational interface; Workflow Designer visual builder; Pipeline Monitor with run timeline and live logs.
- Frontend: `/ai-workspace`, `/monitor`, `/monitor/:runId` routes; artifact card standards for table/chart/code/report; ECharts advanced charts (Sankey, Network, Trend).
- Backend/API: chat/session/upload/signal endpoints; runs signals and signals stream endpoint.
- Data/model/migrations: new tables `chat_sessions`, `chat_messages`, `chat_uploads`, `workflow_signal_events`.
- Security: SQL Server structured form with secret-boundary; SQLite local-dev compatibility hardened for `now()` server default.
- Operations: air-gapped Helm installation guidance; local launcher scripts.
- Documentation: control plane architecture note; release checklist; rollback runbook.

### Public API and Contract Changes

- Added endpoints:
  - `POST/GET/DELETE /v1/chat/sessions*`
  - `POST/GET /v1/chat/sessions/{id}/messages*`
  - `POST/GET /v1/chat/sessions/{id}/uploads*`
  - `POST/GET /v1/runs/{run_id}/signals*`
  - `GET /v1/runs/{run_id}/signals/stream`
- Changed endpoints: (none breaking)
- Deprecated endpoints: (none)
- Compatibility notes: All existing `/v1/runs`, `/v1/workflows`, `/v1/me`, `/v1/auth/*` contracts unchanged.

### Security and Privacy Notes

- Auth/session impact: dev-token auth remains local-only; release requires OIDC.
- Tenant/workspace isolation impact: unchanged from M19; verified via route authorization matrix.
- Secret handling impact: SQL Server passwords now stored via backend secret boundary.
- Upload/artifact safety impact: chat uploads validated through safe render and route-authorized artifact access.
- Accepted/deferred findings: M8 Cloud Run hardening pending Security/SRE approvals; M22 RuntimeEngine default promotion deferred.

### Test Evidence

| Gate | Command or evidence | Result | Notes |
|---|---|---|---|
| Backend (sqlite compat + chat/signals) | `pytest tests/test_sqlite_compat.py tests/test_chat_and_signals.py -q` | Passed | Local SQLite path |
| Backend (workflow lifecycle) | `pytest tests/test_workflow_lifecycle.py -q` | Passed | Full smoke |
| Backend (m5 E2E) | `pytest tests/test_m5_e2e.py -q` | Passed | Backend E2E |
| Frontend typecheck | `npm run typecheck` | Passed | |
| Frontend vitest | `npm run test` | Passed | |
| Frontend build | `npm run build` | Passed with chunk warning | Future code-splitting recommended |

### Known Risks

- Large frontend bundle size warning remains (future code-splitting recommended).
- M8 policy approvals still pending before GA.
- Full TG3/TG4 release-environment execution still pending before GA sign-off.

### Rollback Plan

- Rollback trigger: any P1/P2 within 30 minutes of release; error rate > 1%; latency > 2× baseline.
- Rollback command/procedure: deploy previous revision (see `docs/RELEASE.md` §6.4).
- Data rollback/migration note: `chat_sessions`, `chat_messages`, `chat_uploads`, `workflow_signal_events` migrations are additive; rollback does not require data reversal.
- Verification after rollback: `GET /healthz`, `GET /ready`, login/dev path, `/v1/me`, `/v1/chat/sessions` list, latest `/v1/runs/{id}`, `admin scheduler/DLQ` summary.

### Monitoring and Support

- Dashboard: `/admin` (local); production dashboard URL required before GA.
- Alerts: error rate > 1%, latency P95 > 2× baseline, OIDC JWKS unavailable (returns 503 not 500).
- Logs: Cloud Logging (production), structured JSON to stdout (local).
- On-call/contact: Platform On-call / Rollback Owner (placeholder).
- Incident doc: `apps/platform-api-app/docs/INCIDENT_RESPONSE.md`.

---

**Source consolidation note**

- `docs/release-notes-template.md` → §Template (all subsections).
- `planning_docs/strategy_execution/release_notes_m20_draft.md` → §Example: M20 Release Candidate (v0.20.0-rc1, 2026-03-23) including highlights, API additions, database additions, frontend additions, validation summary, known risks.
