# Platform API (FastAPI)

Multi-tenant backend API for the AI Data Science Team platform.

## Local dev

- Create a virtual env and install dependencies: `pip install -r requirements.txt`
- Run migrations: `alembic upgrade head`
- Preferred local launcher: `start_platform_api_local.cmd`
- Direct run option: `uvicorn platform_api.asgi:app --reload --port 8010`
- Health check: `GET http://127.0.0.1:8010/healthz`
- Backward-compatible alias: `GET http://127.0.0.1:8010/health` (temporary)
- Run smoke test: `python scripts/smoke_test.py`

Alternative (Docker):

- PowerShell: `$env:POSTGRES_PASSWORD='<strong-local-password>'; docker compose up --build`
- cmd.exe: `set POSTGRES_PASSWORD=<strong-local-password> && docker compose up --build`
- Or in PowerShell: `./scripts/run_local.ps1`

Cloud deploy helper (GCP Cloud Run):

- `./scripts/deploy_cloud_run.ps1 -ProjectId <gcp-project> -Region <region>`
- Then apply secret/env mappings per `planning_docs/strategy_execution/cloud_run_hardening_checklist.md`

## Auth

Default is production-safe:

- `DEPLOYMENT_PROFILE=release` + `AUTH_MODE=oidc` (default): validates JWTs using OIDC settings.
- `AUTH_MODE=dev` accepts `Authorization: Bearer dev` only when `DEPLOYMENT_PROFILE=local`.

## Runs API

- Canonical orchestration entrypoint: `POST /v1/runs`
- `/v1/prefect/*` endpoints are compatibility-only and marked deprecated.

## Universal Platform Control Plane

- Catalog: `GET /v1/control-plane/catalog`
- Query: `POST /v1/control-plane/query`
- Action planning: `POST /v1/control-plane/actions/plan`
- Action execution: `POST /v1/control-plane/actions/execute`

This bounded context is independent from the DS/ML agent registry and exists so
chat, future CLI, and future MCP adapters can query platform state through the
same catalog, policy, redaction, and audit rules.

The backend reads the repo-root `.env` through `platform_api.core.config`; keep
real local secrets there only. `apps/platform-api-app/.env.example` is a
template/reference and `apps/platform-api-app/.env` should not be used for
normal local development.
