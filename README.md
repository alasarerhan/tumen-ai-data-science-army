# TÜMEN AI Data Science Platform

TÜMEN AI Data Science Team is an AI-powered analytics platform that helps business users analyze data without writing code.

Users can upload CSV/Excel files, ask questions in natural language (English or Turkish), and get streamed insights, charts, and strategic recommendations. The platform also supports repeatable, scheduled workflows.

## What This Project Includes

- `frontend/`: React + Vite application (AI Workspace, Workflow Designer, Runs, Admin views)
- `apps/`: Backend applications, including the FastAPI platform API
- `ai_data_science_team/`: Agent library, orchestration primitives, connectors, and data science tools
- `docs/`: project and launch documentation
- `tools/`: utility scripts and maintenance helpers

## Core Capabilities

- Conversational analytics with SSE streaming
- Multi-step workflow design and execution
- Scheduled runs (cron-like and natural-language scheduling)
- Artifact generation (tables, charts, reports)
- Tenant-aware architecture for workspace-level isolation
- Admin/operability surfaces (run status, monitoring-oriented views)

## High-Level Architecture

- Frontend: React, TypeScript, Vite, TanStack Query, Radix UI, React Flow, ECharts
- API Layer: FastAPI services for auth, chat, workflows, runs, scheduler, artifacts
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
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_MODEL_STRATEGY`
- `CORS_ORIGINS`
- `PREFECT_DEFAULT_DEPLOYMENT_ID`

Use `.env.example` files in app directories as templates.

## Troubleshooting

- Login issues: verify `AUTH_MODE`, OIDC issuer/audience, and Google OAuth settings
- API 500 errors: check API logs and database connection
- Chat not streaming: verify SSE endpoint health and OpenAI credentials
- Scheduled runs not firing: check Prefect deployment/worker state
- CORS errors: verify frontend origin is included in `CORS_ORIGINS`

## Additional Documentation

- Project deep-dive: `FORME.md`
- Frontend details: `frontend/README.md`
- Backend/app-specific docs: `apps/*/README.md`

