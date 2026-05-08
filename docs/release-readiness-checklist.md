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
| Frontend env file / profile | |
| Backend env file / profile | |
| Auth mode (`dev` or `OIDC`) | |
| Database profile (`SQLite`, local Postgres, release-like Postgres) | |
| Prefect status | |
| Redis / context store status | |
| Object/artifact storage status | |
| Upload scanning dependency status | |
| Frontend URL / port | |
| Backend URL / port | |
| External credentials or secrets required | |
| Known blockers / expected skips | |

## 3. Evidence Matrix

| Gate | Command or check | Preconditions confirmed | Evidence location / output | Owner | Status |
|------|------------------|-------------------------|----------------------------|-------|--------|
| Frontend typecheck | `cd frontend && npm run typecheck` | [ ] | | | |
| Frontend lint | `cd frontend && npm run lint` | [ ] | | | |
| Frontend unit tests | `cd frontend && npm run test` | [ ] | | | |
| Backend pytest | `cd ai-data-science-team/apps/platform-api-app && pytest` | [ ] | | | |
| Agent-library pytest | `cd ai-data-science-team && pytest` | [ ] | | | |
| Playwright golden path | `cd frontend && npm run test:e2e` | [ ] | | | |
| Backend smoke | `/healthz`, `/ready`, `/metrics`, auth path, `/v1/me` | [ ] | | | |
| Frontend smoke | app load, login path, workflow/run path | [ ] | | | |
| Migration check | `cd ai-data-science-team/apps/platform-api-app && alembic upgrade head` | [ ] | | | |

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
