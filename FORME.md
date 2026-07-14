# FORME.md

Plain-language documentation for the TÜMEN AI Data Science Platform.

## 1. The Big Picture (Project Overview)

This project is an agentic data science and machine learning operations platform. In plain English: it helps people design, run, monitor, and govern data analysis or machine learning work without treating every task like a one-off chat. The product has a web interface, a backend API, a workflow engine, and a library of specialist agents that can clean data, analyze it, train models, evaluate models, monitor results, and explain what happened.

The problem it solves is coordination. Data science work usually involves many steps: upload data, inspect it, clean it, choose an analysis path, run a model, check the result, save the useful outputs, and repeat. This platform turns that messy chain of work into visible workflows, tracked runs, reusable artifacts, and human approvals where needed.

Users interact with it through a React web app. They can open dashboards, chat in the AI Workspace, design workflows, trigger runs, inspect run traces, review reports, manage data sources, and watch ModelOps state.

If this were a restaurant, the frontend would be the dining room, the FastAPI backend would be the head waiter and kitchen dispatcher, Prefect would be the kitchen ticket rail, the agent library would be the specialist cooks, and the database would be the filing cabinet where every order, recipe, receipt, and inspection note is kept.

## 2. Technical Architecture - The Blueprint

Simple version:

```text
User browser
    |
    v
React + Vite frontend
    |
    v
FastAPI Platform API
    |
    +--> PostgreSQL / SQLite data store
    +--> Prefect workflow orchestration
    +--> OpenAI / LangChain-powered agents
    +--> Redis, optional cache / queue / runtime state
    +--> Local/S3/GCS artifact storage
```

Building-tour version:

```text
+-------------------+        +-----------------------+
| Frontend           |        | Platform API           |
| React screens      +------->| FastAPI routes         |
| typed API clients  |        | auth, CSRF, limits     |
+-------------------+        +-----------+-----------+
                                          |
               +--------------------------+--------------------------+
               |                          |                          |
               v                          v                          v
       +---------------+          +---------------+          +----------------+
       | Database       |          | Prefect        |          | Agent library  |
       | tenants, runs, |          | creates and    |          | DS/ML workers  |
       | workflows,     |          | reads flow     |          | and chat       |
       | artifacts      |          | runs           |          | routing        |
       +---------------+          +---------------+          +----------------+
               |
               v
       +----------------+
       | Artifacts       |
       | tables, charts, |
       | reports, models |
       +----------------+
```

The frontend is the dining room. It gives users screens such as Dashboard, AI Workspace, Workflows, Runs, Reports, ModelOps, Data Sources, Settings, Monitor, Agents, and Admin. It does not do the serious platform work itself. It calls typed API modules under `frontend/src/app/api/`.

The FastAPI backend is the kitchen dispatcher. It receives requests, checks who the user is, validates workspace access, enforces security middleware, talks to the database, and forwards long-running work to orchestration. The entry point is `apps/platform-api-app/platform_api/asgi.py`, which creates the app from `platform_api.main.create_app()` and enables runtime services.

The database is the filing cabinet. SQLAlchemy models store tenants, users, memberships, workflows, runs, node executions, artifacts, model registry entries, data sources, human approvals, chat sessions, signal events, scheduled jobs, and audit logs.

Prefect is the kitchen ticket rail. When the API creates a run, it asks Prefect to create a flow run from a deployment. That gives the platform an external orchestration ID to track. If the required deployment ID is missing, run creation fails unless local fallback is explicitly enabled.

The agent library is the set of specialist cooks. It contains agents for data cleaning, EDA, SQL analysis, visualization, MLflow, time series, model evaluation, model monitoring, serving, explainability, and orchestration. The `ChatWorkspace` class routes a chat message to a specialist agent and normalizes the result into text plus optional artifacts.

Key architectural choices:

| Decision | Why This and Not the Obvious Alternative? | What Could Go Wrong |
| --- | --- | --- |
| React + Vite frontend | Fast local development and a clear single-page-app structure. A heavier server-rendered framework is not necessary for an internal workflow console. | Large screens can become hard to keep consistent without strong shared components. |
| FastAPI backend | Python fits the data science ecosystem and FastAPI gives typed request/response handling with OpenAPI docs. | Backend and agent code can blur together if service boundaries are not kept clean. |
| SQLAlchemy models | Keeps platform state structured and queryable. A document-only store would make tenant isolation, runs, and audit trails harder to reason about. | JSON fields are used for flexible payloads; too much JSON can make reporting harder later. |
| Prefect orchestration | Long-running DS/ML workflows need a real run engine instead of plain HTTP requests. | Missing deployment IDs or unhealthy workers block run creation/execution. |
| Chat as a control plane, not the whole product | Chat is useful for asking and planning, but the platform still needs explicit workflows, runs, artifacts, approvals, and admin surfaces. | Users may expect chat to perform everything instantly; the UI must make governed actions clear. |
| Plain Python `ChatWorkspace` router | The code comments say this is deliberate: classify intent, pick an agent, invoke it, normalize the artifact. It is predictable and cheap compared with wrapping routing in another agent graph. | Simple routing may be less flexible for deeply ambiguous requests. |
| Root `.env` as the normal local source | One configuration file avoids conflicting frontend/backend settings. | Developers may still create app-local env files and confuse themselves. |

Clever or unusual choices:

- The API includes a Universal Platform Control Plane so chat, future CLI tools, and future MCP-style adapters can query platform state through the same catalog, policy, redaction, and audit rules.
- The run API records both workflow runs and per-node execution rows, so the frontend can show run traces instead of only a single "running/failed" badge.
- Chat streaming uses a durability pattern: save the user message, create a pending assistant message, stream chunks, then update the assistant message at the end. If the server crashes mid-stream, the conversation has a recoverable record.
- Security middleware is intentionally ordered. CORS, idempotency, CSRF, rate limits, request size limits, gzip, and observability all sit in the request path.

## 3. Codebase Structure - The Filing System

Top-level map:

```text
.
|-- ai_data_science_team/        # Core agent library
|   |-- agents/                  # Specialist data and ML agents
|   |-- connectors/              # Data connection abstractions
|   |-- ds_agents/               # Data-science-focused agents
|   |-- ml_agents/               # ML, MLflow, evaluation, time-series agents
|   |-- multiagents/             # Chat workspace and multi-agent orchestration
|   |-- parsers/                 # Parsing helpers
|   |-- templates/               # Prompt/code templates
|   `-- tools/                   # Agent tools
|-- apps/
|   |-- platform-api-app/        # FastAPI backend
|   |-- ai-pipeline-studio-app/  # Example/product app
|   |-- exploratory-copilot-app/ # Example/product app
|   |-- pandas-data-analyst-app/ # Example/product app
|   `-- sql-database-agent-app/  # Example/product app
|-- frontend/                    # React + Vite application
|   |-- src/app/api/             # Typed API clients
|   |-- src/app/screens/         # Main product screens
|   |-- src/app/hooks/           # React data hooks
|   |-- src/app/context/         # Auth context
|   `-- e2e/                     # Playwright tests
|-- docs/                        # Strategy and product docs
|-- tests/                       # Root Python tests
|-- tools/                       # Utility scripts
|-- requirements.txt             # Core Python dependencies
|-- pyproject.toml               # Python package/test metadata
`-- setup.py                     # Package setup metadata
```

`frontend/` is where you go when the screen looks wrong, a button calls the wrong endpoint, or a workflow UI needs to change. Important entry points are `frontend/src/app/App.tsx`, `frontend/src/app/routes.ts`, and `frontend/src/app/api/client.ts`.

`apps/platform-api-app/` is where you go when API behavior, auth, persistence, workflow triggering, schedules, artifacts, or admin surfaces need to change. Important entry points are `platform_api/asgi.py`, `platform_api/main.py`, `platform_api/core/config.py`, and the route files under `platform_api/routes/`.

`ai_data_science_team/` is where you go when the actual data science or ML agent behavior needs to change. Think of this as the professional kitchen behind the platform. The backend can call into it, and example apps can use it directly.

`apps/*-app/` contains product/example applications around the core library. The main production-style API appears to be `apps/platform-api-app/`.

`docs/` contains planning and strategy material. It is useful when you want to understand product intent rather than runtime behavior.

Non-obvious naming conventions:

- `HITL` means "human in the loop", or a human approval checkpoint.
- `ModelOps` means model operations: tracking models, monitoring them, and managing deployment-like state.
- `Control Plane` means a governed way to ask about or act on platform state.
- `Artifact` means a saved output: table, chart, report, dataset, model, metrics file, or similar.
- `flow_key` is the platform's friendly name for what kind of workflow should run; Prefect maps it to a deployment ID.

Known structure mismatch:

- The root README points to `frontend/README.md`, but that file is not present in this checkout. Frontend facts in this document come from `frontend/package.json` and `frontend/src`.

## 4. Connections & Data Flow - How Things Talk to Each Other

### User logs in and opens the app

Simple version: the frontend asks "who am I?", the backend checks auth, and the protected routes either open the app or send the user to login.

Behind the scenes:

1. The browser loads the React app from `frontend/src/app/App.tsx`.
2. `AuthProvider` manages the user's auth state.
3. Routes in `frontend/src/app/routes.ts` wrap most screens in `ProtectedRoute`.
4. API calls go through `frontend/src/app/api/client.ts`.
5. The backend auth layer runs through `platform_api.auth` and `platform_api.authz`.
6. In local development, `AUTH_MODE=dev` can accept a dev token only under the local deployment profile.
7. In release mode, `AUTH_MODE=oidc` validates JWTs using OIDC settings.

What could go wrong:

- If `AUTH_MODE`, `DEPLOYMENT_PROFILE`, OIDC issuer, audience, or JWKS URL are wrong, login fails.
- If CORS origins do not include the frontend URL, the browser blocks requests.
- If CSRF is enabled and the frontend cannot fetch/send the CSRF token, mutations fail with 403.

### User creates or runs a workflow

Simple version: the user designs or selects a workflow, clicks run, and the backend creates a tracked run plus orchestration work.

Behind the scenes:

1. A frontend screen such as Workflows, Workflow Designer, AI Workspace, or Run controls calls a typed API client.
2. The backend receives `POST /v1/runs`.
3. `require_workspace_member` verifies the user belongs to the workspace.
4. If a workflow spec is supplied, the backend loads that saved spec.
5. The backend builds run parameters with the requesting user, trigger type, and input artifact IDs.
6. `create_orchestration_run_id()` asks the selected orchestration adapter to create a run.
7. The default adapter calls Prefect through `PrefectGateway`.
8. The backend creates a `workflow_runs` row and per-node execution rows.
9. The workflow queue service enqueues the run for processing.
10. The frontend can later list runs, open run details, inspect node executions, view artifacts, cancel, retry, or resume from a failed node.

What could go wrong:

- If `PREFECT_DEFAULT_DEPLOYMENT_ID` or a specific deployment ID is missing, Prefect run creation fails.
- If the queue backend is required but unavailable, runs may be recorded but not processed.
- If a workflow spec has broken node references or missing required inputs, validation should catch it before execution, but imported or hand-edited specs still need care.

### User chats with AI Workspace

Simple version: the user sends a message, the platform stores it, routes it to the right specialist, and returns text plus optional artifacts.

Behind the scenes:

1. The AI Workspace screen sends a message to `/v1/chat/sessions/{session_id}/messages` or the streaming endpoint.
2. The backend resolves the user and workspace.
3. The user message is saved.
4. For streaming, a pending assistant message is created before any model work starts.
5. `chat_service` loads session uploads if needed.
6. `ChatWorkspace` classifies intent, picks a specialist agent, invokes it, and normalizes the result.
7. The API stores the assistant response and artifacts.
8. The frontend renders text, tables, charts, code, reports, or workflow design artifacts inline.

What could go wrong:

- If `OPENAI_API_KEY` is missing, model-backed responses fail.
- If upload validation rejects a file extension, MIME type, size, or unsafe archive, the user cannot attach that file.
- If Redis is unavailable, the chat service can fall back to in-memory session state in some paths, but that is not durable across processes.

### External service connections

| Service | Used For | Failure Behavior |
| --- | --- | --- |
| OpenAI | LLM responses and agent reasoning | Chat or agent runs fail or degrade if the key/model is unavailable. |
| Prefect | Creating and reading workflow flow runs | Run creation can fail with an upstream error or validation error. |
| Redis | Optional rate limiting, idempotency, cache, queue, runtime state | Some features fall back; required queue/runtime modes may fail. |
| PostgreSQL / SQLite | Platform state | Most app features fail if the database is unavailable. SQLite is local-friendly; PostgreSQL is the realistic shared deployment target. |
| OIDC provider, default Google | Production authentication | Users cannot log in if issuer/audience/JWKS settings are wrong or provider is down. |
| Object storage: local/S3/GCS | Artifact persistence | Production blocks local artifact storage by configuration; object storage must be configured for production-like operation. |

## 5. Technology Choices - The Toolbox

| Technology | What It Does Here | Why This One | Watch Out For |
| --- | --- | --- | --- |
| Python | Main backend and agent language | Best fit for data science, ML, pandas, LangChain, and FastAPI | Dependency sprawl is easy in agent-heavy projects |
| FastAPI | HTTP API server | Typed endpoints, OpenAPI docs, async support | Middleware order matters |
| SQLAlchemy | Database mapping | Lets Python code work with relational tables cleanly | JSON-in-text fields can become hard to query |
| Alembic | Database migrations | Tracks schema changes over time | Migrations must match models |
| PostgreSQL | Production-style relational database | Strong fit for tenant/workspace/run/audit state | Needs operational setup and backups |
| SQLite | Local development database option | Easy local startup | Not a substitute for production concurrency |
| React | Browser UI | Component model fits dashboards and workflow screens | Large SPAs need careful state boundaries |
| Vite | Frontend build/dev server | Fast dev loop | Production environment variables must be wired correctly |
| TypeScript | Safer frontend JavaScript | Catches many UI/API shape mistakes early | Types can drift if backend schemas change |
| TanStack Query | Frontend server-state cache | Handles loading, caching, and retries for API data | Cache invalidation must be deliberate after mutations |
| React Router | Frontend routing | Clear protected routes and screen mapping | Route guards must stay aligned with auth roles |
| React Flow | Workflow designer graph UI | Natural fit for node-and-edge workflows | Complex graph validation must not live only in the browser |
| ECharts | Charts and metrics | Rich chart rendering for reports and dashboards | Chart payloads need consistent shape |
| Radix UI style components | Accessible UI primitives | Good base for menus, dialogs, controls | Styling consistency still depends on local components |
| LangChain / LangGraph | Agent and LLM workflow building blocks | Common ecosystem for LLM agents | Can add abstraction overhead if overused |
| OpenAI | Model provider | Powers natural-language reasoning and generation | Usage-based cost; requires key and model availability |
| Prefect | Workflow orchestration | Good for long-running, scheduled, observable jobs | Requires deployments/workers to be configured |
| Redis | Cache, queue, rate-limit/idempotency support | Fast shared state for runtime coordination | Optional in some paths, required in others depending on settings |
| Prometheus client | Metrics | Exposes operational measurements | Metrics need dashboards/alerts to become useful |
| Playwright | End-to-end frontend tests | Tests browser behavior | Requires browser dependencies |
| Vitest | Frontend unit tests | Fast React/TypeScript tests | Mocked tests can miss integration problems |
| Pytest | Python tests | Standard Python testing tool | Integration tests may need API keys/services |

Cost implications:

- OpenAI is usage-based and can become meaningful if many chats or agents run large prompts.
- Prefect can be local/self-hosted or cloud-based depending on deployment choice.
- PostgreSQL, Redis, and object storage cost depends on hosting provider and scale.
- Local development can use SQLite and local storage, but production settings intentionally push toward stronger infrastructure.

## 6. Environment & Configuration

The normal local configuration file is the repo-root `.env`. The examples under app folders are templates only.

Important variables:

| Variable | Plain-Language Meaning | Be Careful Because |
| --- | --- | --- |
| `API_HOST`, `API_PORT` | Where the backend listens | Frontend must call the matching URL |
| `DEPLOYMENT_PROFILE` | Whether the app is local, staging, or release-like | Dev auth is only safe in local |
| `AUTH_MODE` | Login mode: dev token or OIDC | Wrong mode can lock users out or weaken security |
| `DEV_AUTH_TOKEN`, `DEV_AUTH_EMAIL` | Local-only test identity | Do not use real production auth this way |
| `OIDC_ISSUER`, `OIDC_AUDIENCE`, `OIDC_JWKS_URL` | Production login verifier settings | Must match the identity provider exactly |
| `DATABASE_URL` | Database connection string | SQLite is convenient; PostgreSQL is safer for shared systems |
| `OPENAI_API_KEY` | Secret key for model calls | Never commit real values |
| `OPENAI_MODEL`, `OPENAI_MODEL_STRATEGY` | Model names for normal and strategy work | Model changes affect quality, latency, and cost |
| `CORS_ORIGINS` | Browser origins allowed to call the API | Missing frontend URL causes browser failures |
| `VITE_API_BASE_URL` | Frontend's backend URL in built deployments | Vite exposes `VITE_` variables to browser code |
| `VITE_AUTH_MODE`, `VITE_DEV_AUTH_TOKEN`, `VITE_OIDC_LOGIN_URL` | Frontend auth behavior | Dev token belongs only in local settings |
| `DATA_SOURCE_SECRET_KEY` | Encrypts stored data source credentials | Losing/changing it can break stored secrets |
| `PREFECT_HELLO_DEPLOYMENT_ID`, `PREFECT_DEFAULT_DEPLOYMENT_ID` | Prefect deployment targets | Missing IDs stop run creation |
| `AGENT_CACHE_REDIS_URL` | Redis for cache/rate/idempotency support | Empty means local/in-memory behavior in some places |
| `ARTIFACT_STORAGE_BACKEND` | `local`, `s3`, or `gcs` artifact storage | Production rejects local artifact storage |
| `CHAT_UPLOAD_DIR`, `CHAT_UPLOAD_MAX_MB` | Where uploads go and how large they may be | Directory must be writable; large uploads increase risk/cost |
| `CSRF_ENABLED`, `CSRF_EXEMPT_PATHS` | Browser mutation protection | Disabling CSRF is risky outside controlled local testing |
| `EGRESS_ALLOWED_HOSTS`, `EGRESS_STRICT_MODE` | Controls outbound network destinations | Too strict can break auth or integrations; too loose increases risk |

Development vs production:

- Local development can run with `DEPLOYMENT_PROFILE=local`, `AUTH_MODE=dev`, SQLite, local uploads, and local artifacts.
- Release-like deployments default to OIDC auth and should use PostgreSQL plus object storage.
- Production profile refuses local artifact storage, which is a good guardrail: model outputs and reports should not live only on one server's disk.

If you need to change where artifacts are stored, update `ARTIFACT_STORAGE_BACKEND` and the matching bucket/local directory variables. Be careful because old artifact URIs may still point to the previous backend.

If you need to change the frontend API URL, update `VITE_API_BASE_URL`. Be careful because Vite variables are baked into the frontend build.

## 7. Lessons Learned - The War Stories

The codebase contains more evidence of architectural learning than a written bug diary. The sections below separate what is explicitly visible in code from reasonable engineering interpretation.

### Bugs & Fixes

**Middleware order was important enough to document in code.** The API comments warn that middleware runs in reverse registration order. The practical lesson: security and observability are not just "turn it on" features. They are a queue at the door. If the bouncer, ticket checker, and notebook keeper stand in the wrong order, either people get blocked incorrectly or the logs miss important context.

**Chat streaming needed durability.** The streaming route saves the user message and creates a pending assistant message before streaming begins. That is a fix for a common failure mode: if a server crashes mid-response, the conversation should not forget that the user asked something.

**Run cancellation needed concurrency care.** The cancel endpoint uses row-level locking and ETags. Plain language: if two people try to change the same run at once, the system tries to avoid letting one stale click overwrite the other.

**Frontend documentation drift exists.** The root README references `frontend/README.md`, but the file is missing. The fix is simple: either add that README or remove the link. The deeper lesson is that documentation should be checked like code.

### Pitfalls & Landmines

Changing auth touches more than one place. Backend `AUTH_MODE`, OIDC settings, frontend auth variables, cookies, CSRF, and protected routes all need to agree.

Changing workflow specs affects the designer, backend validation, run creation, node execution records, artifacts, and run detail screens. A workflow is not just a JSON document; it is also a promise the UI and runtime both depend on.

Changing artifact shape affects reports, run details, ModelOps, AI Workspace rendering, and lineage views. Treat artifact formats like public contracts.

Changing Prefect deployment IDs can quietly break all run creation. The platform maps `flow_key` values to deployment IDs. If the ID is missing, the kitchen ticket never reaches the kitchen.

Redis is optional in some parts and important in others. That flexibility is useful locally, but in shared environments you need to know which features rely on shared runtime state.

### Discoveries

The strongest product discovery is that chat alone is not enough. This platform treats chat as a control plane: useful for asking questions and drafting actions, but not a replacement for visible workflows, approvals, audit logs, and run history.

The strongest engineering discovery is that agent work needs receipts. Runs, node executions, artifacts, lineage, signals, logs, and approvals are all ways of making AI-assisted work inspectable.

If starting over, the main thing to protect early would be contracts: workflow spec schema, artifact schema, run status lifecycle, and API response types. Those contracts are the bones of the product.

### Engineering Wisdom

Use analogies, but build with contracts. A user may think "run my model again," but the system needs exact workspace IDs, workflow versions, input artifact IDs, status transitions, and permissions.

Keep the agent layer and platform layer distinct. Agents do the expert work; the platform governs identity, storage, orchestration, and auditability.

Make failures visible. A failed Prefect run, rejected file upload, expired approval, missing deployment ID, or blocked CSRF token should become a useful message, not a mystery.

Avoid "just one more JSON blob" becoming the database strategy. Flexible JSON is useful for artifacts and parameters, but anything users filter, audit, join, or report on repeatedly may deserve a first-class column/table.

## 8. Quick Reference Card

### Run Locally

Prerequisites:

- Python 3.10 or newer
- Node.js 18 or newer
- Docker Desktop if using a local PostgreSQL stack

Backend:

```bash
cd apps/platform-api-app
start_platform_api_local.cmd
```

Direct backend option:

```bash
cd apps/platform-api-app
uvicorn platform_api.asgi:app --reload --port 8010
```

Frontend:

```bash
cd frontend
start_frontend_local.cmd
```

If the `.cmd` launcher is not suitable for your shell:

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5174
```

Common local URLs:

- Frontend: `http://127.0.0.1:5174`
- API: `http://127.0.0.1:8010`
- API docs: `http://127.0.0.1:8010/docs`
- Health check: `http://127.0.0.1:8010/healthz`

### Common Commands

Backend tests:

```bash
cd apps/platform-api-app
python -m pytest -q
```

Root package tests:

```bash
python -m pytest -q
```

Frontend tests:

```bash
cd frontend
npm run test
```

Frontend typecheck and lint:

```bash
cd frontend
npm run typecheck
npm run lint
```

Frontend end-to-end tests:

```bash
cd frontend
npm run test:e2e
```

Database migrations:

```bash
cd apps/platform-api-app
alembic upgrade head
```

Smoke test:

```bash
cd apps/platform-api-app
python scripts/smoke_test.py
```

### When Something Breaks

Login breaks: check `AUTH_MODE`, `DEPLOYMENT_PROFILE`, OIDC settings, cookies, and CSRF.

Frontend cannot call backend: check `VITE_API_BASE_URL`, dev proxy behavior, backend port, and `CORS_ORIGINS`.

Chat fails: check `OPENAI_API_KEY`, model names, upload validation, backend logs, and whether Redis fallback is acceptable.

Runs fail to start: check Prefect API connectivity, deployment IDs, worker status, and queue settings.

Artifacts do not appear: check artifact records, storage backend, storage directory/bucket, and lineage relationships.

Schedules do not fire: check scheduler runtime, scheduled job rows, queue health, and Prefect worker state.

Admin/operator surfaces fail: verify the user role and workspace/tenant membership.

### Unknowns Not Present in Code

- Production URL
- Staging URL
- Admin dashboard URL outside the app
- Exact hosting provider for production
- Real incident history
- Actual cloud cost numbers

Those should be added when deployment information is available.
