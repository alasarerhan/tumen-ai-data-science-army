# Platform API (FastAPI)

Multi-tenant backend API for the AI Data Science Team platform.

## Local dev

- Create a virtual env and install dependencies: `pip install -r requirements.txt`
- Run migrations: `alembic upgrade head`
- Run the API: `uvicorn platform_api.asgi:app --reload --port 8000`
- Health check: `GET http://localhost:8000/healthz`
- Backward-compatible alias: `GET http://localhost:8000/health` (temporary)
- Run smoke test: `python scripts/smoke_test.py`

Alternative (Docker):

- `docker compose up --build`
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

See `.env.example`.
