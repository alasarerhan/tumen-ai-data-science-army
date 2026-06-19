# Frontend Runbook

> Project introduction + operational runbook for the TUMEN AI Data Science Frontend.
> Replaces `frontend/README.md` and `frontend/docs/runbook-frontend.md`.

## Local Start

```powershell
cd frontend
start_frontend_local.cmd
```

The local app runs at `http://127.0.0.1:5174` and proxies API calls to the platform API at `http://127.0.0.1:8010`.

## Main Screens

- **AI Workspace**: conversational data analysis, uploads, streamed answers, artifacts, and Universal Platform Control Plane query/action results.
- **Workflow Designer**: visual workflow creation, validation, scheduling, and triggering.
- **Runs and Monitor**: execution history, logs, signals, safe agent traces, retry/cancel, and operational state.
- **Agents**: catalog discovery plus first-pass execution summary from Control Plane `run.nodes`.
- **Data Sources**: CSV/Excel/local file, generic SQL URI, SQL Server, and MCP connector setup.
- **Settings**: categorized user, workspace, data source, security, notification, and operations settings.
- **Admin**: scheduler, queue, DLQ, cleanup, and platform health surfaces.

## Environment

Important frontend variables are read from the repo-root `.env` because `vite.config.ts` sets `envDir` to the checkout root. Do not use `frontend/.env` or `frontend/.env.local` for normal local development.

- `VITE_API_BASE_URL`: release API base URL. In local dev the Vite proxy is used.
- `VITE_AUTH_MODE`: local verification uses `dev`; release deployments use OIDC.
- `VITE_DEV_AUTH_TOKEN`: optional local token override for dev login.
- `VITE_OIDC_LOGIN_URL`: release SSO redirect URL.

## Commands

```powershell
npm run typecheck
npm run lint
npm run test
npm run test:e2e
```

`npm run test:e2e` remains a release gate. Repeated local dev-auth attempts can trip API rate limiting, so use a clean local API process or a rate-limit-safe test strategy when validating the full golden path.

## Data Source Notes

SQL Server is configured through a structured form rather than a raw connection URI. Passwords are submitted only to the backend secret boundary and are never returned by the API or shown after submission. Release deployments must set `DATA_SOURCE_SECRET_KEY` so stored SQL Server credentials can be decrypted by the platform API after restart. Generic SQL URI support remains available for other database engines.

## Control Plane Notes

Platform-state questions in AI Workspace render as `platform_query_result` artifacts. The frontend client lives in `src/app/api/controlPlane.ts`, and the generic renderer lives in `src/app/components/chat/ArtifactCard.tsx`. The renderer supports summary, sections, tables, metrics, provenance/redaction notes, links, relationship payloads, and action confirmation blocks. Mutating actions must show confirmation UI before calling `/v1/control-plane/actions/execute`.

## Monitoring

### Error Tracking

- Sentry dashboard: `https://sentry.io/projects/[project-id]`
- Error rate threshold: > 1% of sessions
- Alert channel: `#alerts-frontend` (Slack)

### Performance Metrics

- Web Vitals dashboard: `[Vitals endpoint]`
- Key metrics:
  - **LCP** (Largest Contentful Paint): < 2.5s
  - **FID** (First Input Delay): < 100ms
  - **CLS** (Cumulative Layout Shift): < 0.1

Frontend Web Vitals are captured by `frontend/src/app/lib/web-vitals.ts` and forwarded to the platform's `/v1/telemetry/client-errors` endpoint as `WebVitalMetric` errors with structured context.

## Common Issues

### Login Loops

- Confirm API is running on `127.0.0.1:8010` with `AUTH_MODE=dev` for local verification.
- Check Network tab: `/v1/auth/login/dev` should return 200 with cookie session, then `/v1/me` should return user.

### Data Source Test Failures

- Check connection host/port/database and `DATA_SOURCE_SECRET_KEY` consistency across API restarts.

### E2E Failures

- Verify frontend port `5174`, backend port `8010`, and dev auth rate-limit state.

### High Error Rate

1. Check Sentry for recent errors.
2. Identify error patterns (component, route, browser).
3. Check recent deployments.
4. Rollback if necessary (see Rollback Procedures).

### Performance Degradation

1. Check Web Vitals dashboard.
2. Identify slow routes/components.
3. Check bundle size (should be < 500KB gzipped).
4. Review recent changes for performance regressions.

## Rollback Procedures

### Frontend Rollback (CDN)

```bash
# 1. Identify previous version
git log --oneline -10

# 2. Trigger rollback deployment
npm run deploy:rollback -- --version=[previous-version]

# 3. Verify rollback
curl -I https://app.example.com | grep x-deploy-version
```

### Emergency Rollback

1. Access CDN dashboard.
2. Select "Rollback to previous version".
3. Confirm rollback.
4. Monitor error rates for 15 minutes.

## On-Call Procedures

### Severity Levels

- **P1**: Site down or critical functionality broken.
- **P2**: Significant feature broken, workaround exists.
- **P3**: Minor issue, no immediate impact.

### Escalation Path

1. Frontend on-call engineer.
2. Frontend team lead.
3. Engineering manager.

## Health Checks

### Manual Health Check

- [ ] Login page loads.
- [ ] Dashboard renders.
- [ ] Workflow designer accessible.
- [ ] API calls succeed (check Network tab).

### Automated Health Check

- Endpoint: `/health`
- Expected: `200 OK` with `{ status: "ok" }`

---

**Source consolidation note**

- `frontend/README.md` → §Local Start, §Main Screens, §Environment, §Commands, §Data Source Notes, §Control Plane Notes, §Troubleshooting (login/data source/E2E).
- `frontend/docs/runbook-frontend.md` → §Monitoring, §Common Issues (high error rate, performance degradation), §Rollback Procedures, §On-Call Procedures, §Health Checks.
