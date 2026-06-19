# TUMEN AI Data Science Frontend

React + Vite frontend for the AI Data Science Team platform.

## Local Start

```powershell
cd frontend
start_frontend_local.cmd
```

The local app runs at `http://127.0.0.1:5174` and proxies API calls to the
platform API at `http://127.0.0.1:8010`.

## Main Screens

- AI Workspace: conversational data analysis, uploads, streamed answers, artifacts, and Universal Platform Control Plane query/action results.
- Workflow Designer: visual workflow creation, validation, scheduling, and triggering.
- Runs and Monitor: execution history, logs, signals, safe agent traces, retry/cancel, and operational state.
- Agents: catalog discovery plus first-pass execution summary from Control Plane `run.nodes`.
- Data Sources: CSV/Excel/local file, generic SQL URI, SQL Server, and MCP connector setup.
- Settings: categorized user, workspace, data source, security, notification, and operations settings.
- Admin: scheduler, queue, DLQ, cleanup, and platform health surfaces.

## Environment

Important frontend variables are read from the repo-root `.env` because
`vite.config.ts` sets `envDir` to the checkout root. Do not use
`frontend/.env` or `frontend/.env.local` for normal local development.

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

`npm run test:e2e` remains a release gate. Repeated local dev-auth attempts can
trip API rate limiting, so use a clean local API process or a rate-limit-safe
test strategy when validating the full golden path.

## Data Source Notes

SQL Server is configured through a structured form rather than a raw connection
URI. Passwords are submitted only to the backend secret boundary and are never
returned by the API or shown after submission. Release deployments must set
`DATA_SOURCE_SECRET_KEY` so stored SQL Server credentials can be decrypted by
the platform API after restart. Generic SQL URI support remains available for
other database engines.

## Control Plane Notes

Platform-state questions in AI Workspace render as `platform_query_result`
artifacts. The frontend client lives in `src/app/api/controlPlane.ts`, and the
generic renderer lives in `src/app/components/chat/ArtifactCard.tsx`. The
renderer supports summary, sections, tables, metrics, provenance/redaction
notes, links, relationship payloads, and action confirmation blocks. Mutating
actions must show confirmation UI before calling `/v1/control-plane/actions/execute`.

## Troubleshooting

- Login loops: confirm API is running on `127.0.0.1:8010` with `AUTH_MODE=dev`
  for local verification.
- Data source test failures: check connection host/port/database and
  `DATA_SOURCE_SECRET_KEY` consistency across API restarts.
- E2E failures: verify frontend port `5174`, backend port `8010`, and dev auth
  rate-limit state.
