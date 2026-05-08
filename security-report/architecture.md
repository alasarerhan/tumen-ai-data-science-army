# Architecture Recon Report

## 1. Technology Stack Detection
- Primary languages by file count: Python (277 files), TypeScript/TSX/JS (156 files).
- Primary backend framework: FastAPI in `apps/platform-api-app` (`platform_api/main.py:160`, `platform_api/routes/*.py`).
- Primary frontend framework: React + Vite + React Router (`frontend/package.json`, `frontend/src/app/routes.ts`).
- Package/build tooling:
- Python: `requirements.txt` files across monorepo (`ai-data-science-team/requirements.txt`, app-level requirements).
- Node: `frontend/package.json` + `frontend/package-lock.json`.
- CI/CD: GitHub Actions workflows in `.github/workflows/*.yml`.
- Container/IaC: Dockerfile, docker-compose, Helm chart (`apps/platform-api-app/Dockerfile`, `docker-compose.yml`, `helm/platform/*`).
- Datastores detected:
- PostgreSQL connection defaults (`platform_api/core/config.py:24`, `.env` files).
- SQLite usage in tests/local scripts.
- SQLAlchemy ORM present (`requirements.txt`, `platform_api/db/*`).

## 2. Application Type Classification
- Monorepo with multiple services/apps.
- REST API service: FastAPI platform API (`apps/platform-api-app`).
- Web frontend SPA: React/Vite (`frontend`).
- Data-science agent framework/library plus app shells (`ai_data_science_team`, `apps/*`).

## 3. Entry Points Mapping
- Backend HTTP entry points: 89 route decorators under `platform_api/routes`.
- Representative auth and session entry points:
- `platform_api/routes/auth.py` (`/v1/auth/csrf`, `/v1/auth/login/dev`, `/v1/auth/logout`, `/v1/auth/refresh`).
- Data and workflow entry points:
- `platform_api/routes/chat.py`, `workflows.py`, `runs.py`, `data_sources.py`, `artifacts.py`.
- Frontend entry points:
- React router bootstrapping in `frontend/src/app/routes.ts` and `frontend/src/app/App.tsx`.
- CI/manual deployment entry points:
- `.github/workflows/ci.yml`, `release-gates.yml`, `rollout.yml`.

## 4. Data Flow Map
- Browser -> frontend fetch API clients (`frontend/src/app/api/*.ts`) -> FastAPI routes (`platform_api/routes/*.py`) -> SQLAlchemy services/db models (`platform_api/services/*`, `platform_api/db/*`).
- Auth flow:
- Cookie/Bearer token extraction (`platform_api/auth/dependencies.py:22-27`).
- OIDC verification with JWKS fetch (`platform_api/auth/oidc.py:93-148`).
- Artifact flow:
- Artifact metadata via API, then controlled redirect or internal stream (`platform_api/routes/artifacts.py:87-219`).
- LLM/generated-code flow:
- Generated code executed via sandbox helper (`ai_data_science_team/utils/sandbox.py`) and SQL-agent execution helper (`ai_data_science_team/templates/agent_templates.py:840-942`).

## 5. Trust Boundaries
- Authentication boundary:
- Dev-vs-oidc mode checks in `platform_api/auth/dependencies.py:34-53`.
- Authorization boundary:
- Workspace membership checks via `require_workspace_member` dependency in routes.
- CSRF boundary:
- Middleware + token issue/verify flow (`platform_api/core/csrf.py`, `platform_api/routes/auth.py`).
- CORS boundary:
- Config-driven allowed origins with credentials (`platform_api/main.py:190-195`, `platform_api/core/config.py:28`).
- Egress boundary:
- Outbound URL host allowlist enforcement (`platform_api/core/egress_policy.py:30-52`).

## 6. External Integrations
- OIDC identity provider (`accounts.google.com`) via JWKS HTTP fetch.
- OpenAI API key configuration (`.env`, config settings).
- Optional cloud/object storage URI handling in artifact access logic.
- Slack webhook integration in CI workflows.

## 7. Authentication Architecture
- Mixed model:
- OIDC mode for production (`AUTH_MODE=oidc` default in config).
- Dev mode for local profile only with explicit guard (`auth.py`, `dependencies.py`).
- Session/token handling:
- HttpOnly secure cookie for access token (`platform_api/routes/auth.py:39-47`).
- CSRF cookie+header validation for mutating requests (`platform_api/core/csrf.py`).

## 8. File Structure Analysis
- Sensitive configuration files present:
- `ai-data-science-team/.env`
- `ai-data-science-team/apps/platform-api-app/.env`
- Security-sensitive infrastructure files:
- `.github/workflows/*.yml`
- `apps/platform-api-app/Dockerfile`
- `apps/platform-api-app/docker-compose.yml`
- `apps/platform-api-app/helm/platform/*`

## 9. Detected Security Controls
- CSRF protection middleware and token rotation.
- CORS allowlist configuration (non-wildcard by default).
- Rate limiting middleware.
- Egress host allowlist enforcement for OIDC/artifact redirects.
- Artifact file streaming path traversal check (`is_relative_to` guard in `routes/artifacts.py:189`).
- Security headers for streamed files (`X-Content-Type-Options`, CSP, `X-Frame-Options`).

## 10. Language Detection Summary
- Python (~64% by source file count) -> activates `sc-lang-python`.
- TypeScript/JavaScript (~36% by source file count) -> activates `sc-lang-typescript`.

## Recon Notes
- Generated/test-heavy repository; false positives likely in test fixtures and local-dev artifacts.
- Dependency CVE tooling (`pip_audit`, `safety`) was unavailable in this environment; dependency audit used static manifest/workflow analysis.
