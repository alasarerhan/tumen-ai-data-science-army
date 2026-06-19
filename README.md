# TÜMEN AI Data Science Platform

TÜMEN AI Data Science Team is an agentic data science and ML operations platform.

The core product is not a chat application. Users design, run, monitor, debug, and automate data science and machine learning work through governed agent workflows. Chat remains an important interface, but its strategic role is the control plane: users query authorized platform state and plan governed operational actions through the Universal Platform Control Plane catalog.

## What This Project Includes

- `frontend/`: React + Vite application (AI Workspace, Workflow Designer, Runs, Admin views)
- `apps/`: Backend applications, including the FastAPI platform API
- `ai_data_science_team/`: Agent library, orchestration primitives, connectors, and data science tools
- `docs/`: project and launch documentation
- `tools/`: utility scripts and maintenance helpers

## Core Capabilities

- Agentic DS/ML workflow design and execution
- Universal Platform Control Plane for catalog-backed workflow, run, artifact, admin/ops, release-doc, and governed action questions
- CSV/Excel uploads and SQL Server data source setup for governed analysis
- Scheduled runs (cron-like and natural-language scheduling)
- Artifact generation (tables, charts, reports) plus first-pass Reports artifact lineage and output board
- Run monitoring, signals, retry/cancel, and HITL approvals
- Agent discovery, catalog browsing, trace-backed cockpit metrics, Run Detail Trace Inspector, first-pass workflow run matrix, and first-pass artifact lineage/output inspection
- Tenant-aware architecture for workspace-level isolation
- Admin/operability surfaces (run status, monitoring-oriented views)
- Categorized settings for user, workspace, data source, security, notification, and operations configuration

## High-Level Architecture

- Frontend: React, TypeScript, Vite, TanStack Query, Radix UI, React Flow, ECharts
- API Layer: FastAPI services for auth, chat, Universal Platform Control Plane, workflows, runs, scheduler, artifacts
- Data Layer: PostgreSQL for core entities and run history
- Orchestration: Prefect-based run/schedule orchestration
- AI Layer: multi-agent workflows powered by OpenAI models
- Optional Caching: Redis

## Quick Start (Local Development)

## Prerequisites

- Python 3.10+
- Node.js 18+
- Docker Desktop (for local PostgreSQL stack)

## 1) Start Backend

```bash
cd apps/platform-api-app
start_platform_api_local.cmd
```

The local launcher sets `DEPLOYMENT_PROFILE=local`, `AUTH_MODE=dev`,
`DEV_AUTH_TOKEN=dev`, `DATABASE_URL=sqlite:///./platform_dev.db`, and runs
`platform_api.asgi:app` on `http://127.0.0.1:8010`.

## 2) Start Frontend

```bash
cd frontend
start_frontend_local.cmd
```

Frontend local URL: `http://127.0.0.1:5174`
API local URL: `http://127.0.0.1:8010`
API docs: `http://127.0.0.1:8010/docs`

## Useful Commands

```bash
# backend tests
cd apps/platform-api-app
python -m pytest -q

# frontend tests
cd frontend
npm run test

# frontend lint/typecheck
npm run lint
npm run typecheck
```

## Environment Notes

Important variables used across local/release profiles:

- `DEPLOYMENT_PROFILE` (`local` or `release`)
- `AUTH_MODE` (`dev` or `oidc`)
- `DATABASE_URL`
- `DATA_SOURCE_SECRET_KEY`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_MODEL_STRATEGY`
- `CORS_ORIGINS`
- `PREFECT_DEFAULT_DEPLOYMENT_ID`

Use the repo-root `.env` as the single local environment file. App-directory
`.env.example` files are templates only; do not create separate
`frontend/.env`, `frontend/.env.local`, or `apps/platform-api-app/.env` files for
normal local development.

## Troubleshooting

- Login issues: verify `AUTH_MODE`, OIDC issuer/audience, and Google OAuth settings
- API 500 errors: check API logs and database connection
- Chat not streaming: verify SSE endpoint health and OpenAI credentials
- Scheduled runs not firing: check Prefect deployment/worker state
- CORS errors: verify frontend origin is included in `CORS_ORIGINS`

## Additional Documentation

- Project deep-dive: `FORME.md`
- Product strategy and roadmap: `docs/product-strategy-agentic-dsml-platform.md`
- Universal Platform Control Plane: `docs/universal-platform-control-plane.md`
- Frontend details: `frontend/README.md`
- Backend/app-specific docs: `apps/*/README.md`

