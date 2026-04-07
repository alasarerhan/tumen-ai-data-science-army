# FORME.md — The AI Data Science Team Platform

*Everything you need to understand this project, explained in plain language.*

---

## 1. The Big Picture (Project Overview)

**AI Data Science Team** is a platform that lets business users talk to their data like they'd talk to a data scientist. Upload a spreadsheet, ask questions in plain English (or Turkish), and get back charts, insights, and strategic recommendations — no coding required.

Think of it as hiring a team of AI specialists who never sleep: one cleans your messy data, another finds patterns, a third builds predictive models, and a fourth writes up the business implications. You just describe what you want; they figure out how to do it.

**What problem this solves and for whom:**

Business analysts, operations managers, and executives have data but lack the technical skills to extract insights. They either wait weeks for the data science team or make decisions on gut feeling. This platform gives them an AI-powered data science team on demand — upload data, ask questions, get answers with visualizations and recommendations.

**How users interact with it (the user journey):**

1. **Sign in** through Google (your company email becomes your identity)
2. **Create a workspace** — think of it as a project folder for a specific business problem
3. **Upload data** — drag and drop a CSV or Excel file into the AI Workspace chat
4. **Ask questions** — "Which products are declining?", "Predict next quarter's revenue", "What's causing customer churn?"
5. **Review results** — the AI responds with tables, charts, and written analysis
6. **Iterate** — ask follow-up questions, request different visualizations, or ask for strategic recommendations
7. **Build workflows** — for repeatable analyses, use the Workflow Designer to create automated pipelines that run on a schedule

**If this were a restaurant:**

Imagine a restaurant where you're the customer and the kitchen is staffed entirely by AI chefs, each with a specialty:

- **You (the customer)** walk in and describe what you want: "I have these ingredients (your data) and I want a meal that highlights what's working and what's not (your analysis request)."
- **The Maître d' (Chat Router)** listens to your request and decides which chef should handle it — the pastry chef for desserts (visualizations), the sous chef for prep work (data cleaning), or the head chef for the main course (modeling).
- **The Kitchen (Agent System)** is divided into stations: prep (data cleaning), cooking (analysis), plating (visualization), and menu design (strategic recommendations).
- **The Order System (Orchestration)** ensures your order goes through each station in the right sequence, with timing and retries if something goes wrong.
- **The Filing Cabinet (Database)** stores every order, every recipe, and every result so you can revisit them later.
- **The Private Dining Room (Multi-tenancy)** ensures that when you order, only you see your food — other customers' orders are completely separate.

---

## 2. Technical Architecture — The Blueprint

### The Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER'S BROWSER                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ AI Workspace│  │  Workflow   │  │   Runs      │  │     Admin Dashboard │ │
│  │   (Chat)    │  │  Designer   │  │   Monitor   │  │   (FinOps/Health)   │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
└─────────┼────────────────┼────────────────┼────────────────────┼───────────┘
          │                │                │                    │
          ▼                ▼                ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React + Vite)                               │
│  • React Router for navigation                                               │
│  • TanStack Query for data fetching & caching                                │
│  • Radix UI components (buttons, dialogs, forms)                            │
│  • React Flow for workflow visualization                                     │
│  • Monaco Editor for YAML editing                                            │
│  • ECharts for data visualizations                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ HTTP + SSE (Server-Sent Events)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     PLATFORM API (FastAPI Backend)                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │   Auth       │  │   Chat       │  │  Workflows   │  │     Runs       │  │
│  │  (OIDC/JWT)  │  │  (SSE Stream)│  │  (CRUD)      │  │  (Orchestration)│  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │  Scheduler   │  │   HITL       │  │  Artifacts   │  │    Admin       │  │
│  │  (Cron Jobs) │  │  (Approvals) │  │  (Files)     │  │  (FinOps)      │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └────────────────┘  │
│                                                                              │
│  MIDDLEWARE: Rate Limiting → Request Size Limit → CORS → Gzip → Logging    │
└─────────────────────────────────────────────────────────────────────────────┘
          │                         │                         │
          ▼                         ▼                         ▼
┌─────────────────┐    ┌─────────────────────┐    ┌─────────────────────────┐
│   PostgreSQL    │    │   Prefect Cloud     │    │   AI Agent System       │
│   (Database)    │    │   (Orchestrator)    │    │   (Python Library)      │
│                 │    │                     │    │                         │
│ • Tenants       │    │ • Schedule runs     │    │ • Data Cleaning Agent   │
│ • Users         │    │ • Retry logic       │    │ • Visualization Agent   │
│ • Workspaces    │    │ • Queue management  │    │ • ML Training Agent     │
│ • Workflows     │    │ • Run history       │    │ • Strategic Agent        │
│ • Runs          │    │ • Worker pools      │    │ • SQL Analyst           │
│ • Chat Sessions │    │                     │    │ • Orchestrator Agent    │
│ • Audit Logs    │    │                     │    │ • ChatWorkspace Router  │
└─────────────────┘    └─────────────────────┘    └─────────────────────────┘
          │                         │                         │
          ▼                         ▼                         ▼
┌─────────────────┐    ┌─────────────────────┐    ┌─────────────────────────┐
│   GCS / Local   │    │   OpenAI API        │    │   Redis (Optional)      │
│   (Artifacts)   │    │   (LLM Provider)    │    │   (Agent Cache)         │
│                 │    │                     │    │                         │
│ • CSV uploads   │    │ • GPT-4o-mini       │    │ • Response caching      │
│ • Charts        │    │ • GPT-3.5-turbo     │    │ • Rate limit counters   │
│ • Reports       │    │                     │    │                         │
└─────────────────┘    └─────────────────────┘    └─────────────────────────┘
```

### The Building Tour

**The Front Desk (Frontend — React)**

This is what users see and touch. Built with React, it's a single-page application that never reloads — everything updates smoothly as users interact. The frontend talks to the backend through HTTP requests and SSE streams.

*Why React and not something simpler?* The interface needs real-time updates (chat streaming), complex visualizations (workflow designer with drag-and-drop nodes), and interactive charts. React's component model handles this complexity well, and the ecosystem (Radix UI, React Flow, ECharts) provides pre-built solutions for each challenge.

**The Kitchen (Platform API — FastAPI)**

All the real work happens here. FastAPI is a Python web framework that's fast (as the name suggests) and enforces type safety — if you send the wrong data, it rejects it before it reaches your code. The API is organized into "routes" (endpoints), each handling a specific concern:

- `/v1/chat/*` — conversations with AI
- `/v1/workflows/*` — saving and loading workflow definitions
- `/v1/runs/*` — triggering and monitoring pipeline executions
- `/v1/scheduler/*` — cron-based scheduling

*Why FastAPI and not Django?* Django is a full framework with opinions about everything (database, admin panel, auth). FastAPI is minimal — it handles HTTP and gets out of your way. For a microservices-style architecture where we control all the pieces, this flexibility is valuable.

**The Filing Cabinet (PostgreSQL)**

Every piece of data lives here: users, workspaces, workflows, runs, chat messages, audit logs. PostgreSQL is a relational database — think of it as a collection of spreadsheets where rows in one sheet can reference rows in another.

*Why PostgreSQL and not MongoDB?* Our data is highly relational: a tenant has workspaces, workspaces have workflows, workflows have runs, runs have artifacts. PostgreSQL handles these relationships natively with JOINs and foreign keys. MongoDB would require us to manage relationships manually in application code. Also, PostgreSQL's Row-Level Security (RLS) lets us enforce tenant isolation at the database level — even if the API has a bug, one tenant can never see another's data.

**The Order Coordinator (Prefect)**

When a user schedules a workflow to run every Monday at 8 AM, Prefect handles it. Prefect is a workflow orchestrator — it queues jobs, retries on failure, tracks history, and manages concurrent execution limits.

*Why Prefect and not Celery?* Celery is a task queue — it runs jobs but doesn't understand workflows (sequences of dependent tasks). Prefect knows that "clean data" must complete before "train model" can start. It also provides a UI for monitoring and a cloud option that reduces operational burden.

**The Specialist Team (AI Agents)**

This is the secret sauce. The platform includes a library of AI "agents" — specialized AI assistants that each do one thing well:

- **Data Cleaning Agent**: Fixes missing values, corrects data types, removes outliers
- **Data Wrangling Agent**: Transforms and reshapes data
- **Visualization Agent**: Creates charts and graphs
- **ML Training Agent**: Builds predictive models using H2O
- **Strategic Agent**: Synthesizes results into business recommendations
- **SQL Analyst**: Answers questions by querying databases
- **Orchestrator Agent**: Coordinates multiple agents for complex tasks

*Why multiple agents and not one big agent?* Specialization improves quality. A data cleaning agent trained on cleaning tasks outperforms a generalist trying to do everything. Also, this is more cost-efficient — simple tasks use cheaper models, complex tasks use expensive ones.

**The Real-Time Stream (SSE — Server-Sent Events)**

When you chat with the AI, responses stream in word by word, not all at once. SSE is the technology that makes this possible — it's a one-way pipe from server to client that stays open, pushing updates as they happen.

*Why SSE and not WebSockets?* WebSockets are bidirectional (both sides can talk), but we only need server-to-client streaming. SSE is simpler, works through firewalls and proxies, and has native browser support. Less complexity = fewer things that can break.

### Architectural Decisions — Why This and Not That?

| Decision | Why This Choice | What We Gave Up |
|----------|-----------------|-----------------|
| **FastAPI over Django** | Minimal framework, async support, type safety | No built-in admin panel, auth, or ORM |
| **PostgreSQL over MongoDB** | Relational data, ACID transactions, RLS for security | Harder horizontal scaling |
| **Prefect over Airflow** | Python-native, lighter weight, cloud option | Smaller community, fewer pre-built operators |
| **SSE over WebSockets** | Simpler, works through proxies, native browser support | Unidirectional only |
| **React over Vue** | Larger ecosystem, more component libraries | Steeper learning curve |
| **OIDC over custom auth** | Delegated to Google, no password management | Dependency on external provider |
| **LangGraph over raw LangChain** | Stateful agent coordination, visual debugging | Additional abstraction layer |

### Clever Choices Worth Noting

**Hybrid Orchestration**: We use two orchestration systems — LangGraph for interactive chat (real-time, stateful, agent routing) and Prefect for production runs (scheduled, retried, monitored). This seems redundant but serves different needs: chat needs immediate feedback; scheduled runs need reliability guarantees.

**Agent Registry Pattern**: Every agent registers itself with metadata (capabilities, cost tier, input/output schemas). The orchestrator queries this registry to find the right agent for a task. This makes the system extensible — add a new agent, register it, and it's automatically available.

**Workflow Signals (HITL)**: Human-in-the-loop isn't blocking. The pipeline runs, and if a human wants to intervene, they send a "signal" that the pipeline can react to. This avoids the complexity of pausing and resuming workflows.

**Multi-Tenant Isolation at Database Level**: Row-Level Security (RLS) policies in PostgreSQL ensure that even if the API has a bug, one tenant's queries can never return another tenant's data. Defense in depth.

---

## 3. Codebase Structure — The Filing System

### The Folder Map

```
AI_DATASCIENCE_TEAM/
├── frontend/                          # The React web application
│   ├── src/
│   │   ├── app/
│   │   │   ├── screens/               # Page-level components
│   │   │   │   ├── AIWorkspace.tsx    # Chat interface
│   │   │   │   ├── WorkflowDesigner.tsx # Visual workflow builder
│   │   │   │   ├── RunsList.tsx       # Pipeline execution history
│   │   │   │   ├── Dashboard.tsx      # Overview page
│   │   │   │   └── ...
│   │   │   ├── components/            # Reusable UI components
│   │   │   │   ├── ui/                # Generic components (buttons, inputs)
│   │   │   │   ├── chat/              # Chat-specific components
│   │   │   │   ├── workflow/          # Workflow-specific components
│   │   │   │   └── charts/            # Visualization components
│   │   │   ├── context/               # React context providers
│   │   │   │   └── AuthContext.tsx    # Authentication state
│   │   │   ├── api/                   # API client functions
│   │   │   └── utils/                 # Helper functions
│   │   ├── styles/                    # CSS and Tailwind config
│   │   └── main.tsx                   # Application entry point
│   ├── package.json                   # JavaScript dependencies
│   └── vite.config.ts                 # Build configuration
│
├── ai-data-science-team/              # The Python backend and agent library
│   ├── apps/
│   │   └── platform-api-app/          # FastAPI backend service
│   │       ├── platform_api/
│   │       │   ├── routes/            # API endpoints
│   │       │   │   ├── chat.py       # Chat sessions and streaming
│   │       │   │   ├── workflows.py   # Workflow CRUD
│   │       │   │   ├── runs.py       # Pipeline execution
│   │       │   │   └── ...
│   │       │   ├── services/          # Business logic
│   │       │   ├── db/                # Database models and session
│   │       │   │   └── models.py     # SQLAlchemy table definitions
│   │       │   ├── core/               # Cross-cutting concerns
│   │       │   │   ├── config.py      # Environment configuration
│   │       │   │   ├── rate_limit.py  # Request throttling
│   │       │   │   └── observability.py # Logging and metrics
│   │       │   ├── auth/              # Authentication logic
│   │       │   └── orchestration/     # Prefect integration
│   │       ├── alembic/               # Database migrations
│   │       │   └── versions/          # Migration scripts
│   │       ├── tests/                 # Backend tests
│   │       └── requirements.txt       # Python dependencies
│   │
│   └── ai_data_science_team/          # The agent library
│       ├── agents/                    # Individual AI agents
│       │   ├── data_cleaning_agent.py
│       │   ├── data_visualization_agent.py
│       │   ├── orchestrator_agent.py
│       │   └── ...
│       ├── multiagents/               # Multi-agent systems
│       │   ├── chat_workspace.py      # Conversational orchestrator
│       │   ├── chat_router.py         # Intent classification
│       │   └── pandas_data_analyst.py # Data analysis team
│       ├── tools/                     # Agent tools (functions they can call)
│       │   ├── cleaning.py
│       │   ├── visualization/
│       │   └── ...
│       └── orchestration.py           # M22 orchestration primitives
│
├── .claude/skills/                    # AI coding assistant instructions
├── .github/workflows/                 # CI/CD pipelines
├── STRATEGY.md                        # Strategic planning document
└── pyproject.toml                     # Python project configuration
```

### What Lives Where

**`frontend/src/app/screens/`** — The pages users see. Each file is a complete screen: AIWorkspace is the chat interface, WorkflowDesigner is the visual builder, RunsList shows execution history. Open this folder when you need to change what a page looks like or how users interact with it.

**`frontend/src/app/components/`** — Reusable building blocks. The `ui/` subfolder contains generic components (buttons, inputs, dialogs) that could be used anywhere. The `chat/` and `workflow/` subfolders contain domain-specific components. Open this folder when you need to fix a button or add a new type of chart.

**`frontend/src/app/api/`** — Functions that call the backend. Each file corresponds to a backend route group. Open this folder when the frontend isn't talking to the backend correctly.

**`ai-data-science-team/apps/platform-api-app/platform_api/routes/`** — API endpoints. Each file defines the URLs the frontend can call. `chat.py` handles `/v1/chat/*`, `workflows.py` handles `/v1/workflows/*`. Open this folder when you need to add a new API endpoint or fix request/response handling.

**`ai-data-science-team/apps/platform-api-app/platform_api/services/`** — Business logic. Routes delegate to services for the actual work. `chat_service.py` handles chat logic, `run_service.py` handles pipeline execution. Open this folder when you need to understand or modify how something actually works.

**`ai-data-science-team/apps/platform-api-app/platform_api/db/models.py`** — Database schema. Every table is defined here as a Python class. Open this file when you need to add a new table or understand what columns exist.

**`ai-data-science-team/apps/platform-api-app/alembic/versions/`** — Database migrations. Each file is a numbered change to the database schema. Open this folder when you need to see how the database evolved or add a new migration.

**`ai-data-science-team/ai_data_science_team/agents/`** — Individual AI agents. Each file is a specialist: cleaning, visualization, ML, etc. Open this folder when you need to modify how an agent works or add a new one.

**`ai-data-science-team/ai_data_science_team/multiagents/`** — Agent teams and coordinators. `chat_workspace.py` is the main conversational interface; `chat_router.py` decides which agent handles each message. Open this folder when you need to change how agents work together.

### Entry Points — Where Things Start

**Frontend**: `frontend/src/main.tsx` — This is the first code that runs. It mounts the React app into the HTML page.

**Backend**: `ai-data-science-team/apps/platform-api-app/platform_api/main.py` — This creates the FastAPI application, registers all routes, and starts the server.

**Agent Library**: `ai-data-science-team/ai_data_science_team/__init__.py` — This exports the public API of the agent library.

### Naming Conventions

- **Routes**: Named after the resource they manage (`chat.py`, `workflows.py`)
- **Services**: Named after the domain (`chat_service.py`, `run_service.py`)
- **Models**: Singular nouns (`User`, `Workspace`, `WorkflowRun`)
- **Agents**: Descriptive names ending in `_agent.py` (`data_cleaning_agent.py`)
- **Tests**: Mirror the source structure with `test_` prefix (`test_chat_service.py`)

---

## 4. Connections & Data Flow — How Things Talk to Each Other

### User Journey 1: Chatting with AI

When a user asks "What are my top-selling products?", here's what happens:

```
1. USER TYPES MESSAGE
   └── AIWorkspace.tsx captures input, calls streamChatMessage()

2. FRONTEND SENDS REQUEST
   └── POST /v1/chat/sessions/{id}/messages/stream
   └── Body: { workspace_id, content: "What are my top-selling products?" }

3. BACKEND RECEIVES REQUEST
   └── chat.py validates the user has access to this session
   └── Creates a "pending" message in the database (for durability)

4. CHAT SERVICE PROCESSES
   └── chat_service.py calls ChatWorkspace.chat()
   └── ChatWorkspace asks IntentRouter: "What kind of question is this?"
   └── IntentRouter returns: "pandas_data_analyst" (data analysis question)

5. AGENT EXECUTES
   └── PandasDataAnalyst is instantiated
   └── It loads the uploaded DataFrame from the session
   └── It generates Python code to find top-selling products
   └── It executes the code and gets results

6. RESPONSE STREAMS BACK
   └── The agent's response is streamed word-by-word via SSE
   └── Each chunk: data: {"type": "delta", "delta": "The top-selling..."}
   └── Final message includes artifacts (table data, chart config)

7. FRONTEND RENDERS
   └── ChatMessage component displays the text
   └── ArtifactCard component renders the table/chart
   └── Message is saved to database for history
```

**What could go wrong:**

- **OpenAI API timeout**: The agent retries with exponential backoff. If it fails after 3 attempts, the user sees an error message and can retry.
- **Invalid data**: If the uploaded file is corrupted, the agent reports the issue and suggests fixes.
- **Session expired**: The frontend detects a 401 response and redirects to login.

### User Journey 2: Creating and Running a Workflow

When a user builds an automated pipeline:

```
1. USER OPENS WORKFLOW DESIGNER
   └── WorkflowDesigner.tsx loads with empty canvas
   └── Palette shows available node types (Data Loader, Cleaner, etc.)

2. USER DRAGS NODES ONTO CANVAS
   └── React Flow manages the visual graph
   └── Each node represents an agent step
   └── Edges represent data flow between steps

3. USER CONFIGURES SCHEDULE
   └── User types "every Monday at 8am"
   └── NaturalScheduleInput sends to /v1/scheduler/parse
   └── Backend converts to cron: "0 8 * * 1"

4. USER CLICKS "SAVE DRAFT"
   └── POST /v1/workflows with the workflow spec
   └── Backend validates the spec structure
   └── WorkflowSpec record created in database

5. USER CLICKS "SCHEDULE"
   └── POST /v1/scheduler/deployments
   └── Backend creates a Prefect deployment
   └── Prefect registers the cron schedule

6. SCHEDULED RUN TRIGGERS (Monday 8am)
   └── Prefect worker picks up the scheduled job
   └── POST /v1/runs to start execution
   └── RuntimeEngine loads the workflow spec

7. WORKFLOW EXECUTES
   └── Step 1: Data Loader Agent fetches data
   └── Step 2: Data Cleaner Agent processes
   └── Step 3: ML Agent trains model
   └── Step 4: Strategic Agent writes report
   └── Each step's output feeds into the next

8. USER VIEWS RESULTS
   └── RunsList shows the completed run
   └── RunDetail shows step-by-step execution
   └── Artifacts (charts, reports) are downloadable
```

**What could go wrong:**

- **Prefect is down**: The run is queued locally and retried when Prefect recovers.
- **Agent fails mid-pipeline**: The run is marked as "failed" with error details. The user can retry from the failed step.
- **Schedule conflict**: If two workflows try to run simultaneously, queue limits prevent resource exhaustion.

### User Journey 3: Authentication Flow

```
1. USER VISITS THE APP
   └── Frontend checks AuthContext for existing session
   └── No session found → redirect to /login

2. USER CLICKS "SIGN IN WITH GOOGLE"
   └── Frontend redirects to Google OAuth consent screen
   └── User authenticates with Google

3. GOOGLE REDIRECTS BACK
   └── URL includes authorization code
   └── Frontend exchanges code for JWT token
   └── JWT stored in browser (memory, not localStorage for security)

4. SUBSEQUENT REQUESTS
   └── Every API request includes: Authorization: Bearer {jwt}
   └── Backend validates JWT signature with Google's public keys
   └── JWT contains: user_id (sub), email, expiration

5. BACKEND CREATES/LOOKS UP USER
   └── If new user: User record created
   └── If existing user: User record retrieved
   └── User's tenant/workspace memberships loaded

6. REQUEST IS AUTHORIZED
   └── Every route checks: Does this user have access to this workspace?
   └── If yes: request proceeds
   └── If no: 403 Forbidden returned
```

**What could go wrong:**

- **JWT expired**: Backend returns 401, frontend refreshes token or redirects to login.
- **Google is down**: Users can't sign in. No fallback authentication (by design — we don't want to manage passwords).
- **User removed from tenant**: Next request returns 403, user sees "Access denied" message.

### External Service Connections

| Service | Purpose | What Happens If It Fails |
|---------|---------|--------------------------|
| **OpenAI API** | Powers all AI agents | Agents return error; user can retry. Cached responses used when available. |
| **Prefect Cloud** | Schedules and runs workflows | Scheduled runs queue locally; manual runs fail immediately. |
| **Google OAuth** | User authentication | Users cannot sign in. No fallback. |
| **PostgreSQL** | All persistent data | Entire platform is down. No data can be read or written. |
| **Redis** (optional) | Agent response caching | Slower responses (no cache hit), but platform still works. |

---

## 5. Technology Choices — The Toolbox

| Technology | What It Does Here | Why This One | Watch Out For |
|------------|-------------------|--------------|---------------|
| **React 18** | Builds the user interface | Largest ecosystem, component model fits our needs, team familiarity | Requires build step; learning curve for complex state |
| **Vite** | Builds and serves the frontend | Fast dev server, simple config, native ES modules | Different from Webpack; some plugins incompatible |
| **TypeScript** | Type-safe JavaScript | Catches bugs at compile time, better IDE support | Adds complexity; some libraries lack types |
| **TanStack Query** | Data fetching and caching | Handles loading/error states, automatic refetching, optimistic updates | Learning curve for cache invalidation patterns |
| **Radix UI** | Accessible UI components | Unstyled, accessible primitives we can customize | Requires styling; not a complete design system |
| **React Flow** | Workflow visualization | Drag-and-drop nodes, handles connections, minimap | Performance with many nodes; custom node complexity |
| **Monaco Editor** | YAML/code editing | Same editor as VS Code, syntax highlighting, validation | Large bundle size; complex configuration |
| **ECharts** | Data visualizations | Rich chart types, good performance, customizable | Different API from D3; some chart types limited |
| **FastAPI** | Backend web framework | Async support, automatic OpenAPI docs, type validation | Less batteries-included than Django |
| **SQLAlchemy** | Database ORM | Mature, flexible, supports both simple and complex queries | Can be verbose; N+1 query pitfalls |
| **Alembic** | Database migrations | Auto-generates migrations from model changes | Migration conflicts in team development |
| **Pydantic** | Data validation | Type-safe parsing, clear error messages | Performance overhead for large payloads |
| **PostgreSQL** | Primary database | ACID compliance, RLS for security, JSONB for flexibility | Harder to scale horizontally than NoSQL |
| **Prefect** | Workflow orchestration | Python-native, cloud option, built-in UI | Newer than Airflow; smaller community |
| **LangChain** | LLM application framework | Agent abstractions, tool integration, memory management | Rapidly changing API; abstraction leaks |
| **LangGraph** | Stateful agent coordination | Visual debugging, state management, human-in-the-loop | Additional complexity over raw LangChain |
| **OpenAI API** | LLM provider | Best-in-class models, function calling, structured output | Cost per token; rate limits; dependency on external service |
| **SSE** | Real-time streaming | Native browser support, simple HTTP, auto-reconnection | Unidirectional only; connection limits |
| **Docker** | Containerization | Consistent environments, easy deployment | Windows filesystem performance; learning curve |
| **GitHub Actions** | CI/CD | Integrated with GitHub, matrix builds, secrets management | YAML complexity; debugging failures |

### Cost Implications

| Service | Cost Model | Estimated Monthly Cost |
|---------|------------|----------------------|
| **OpenAI API** | Per-token usage | $50-500 depending on usage |
| **Prefect Cloud** | Free tier + paid plans | $0-100 |
| **PostgreSQL (Cloud SQL)** | Instance + storage | $50-200 |
| **Google Cloud Run** | CPU + memory + requests | $20-100 |
| **Google Cloud Storage** | GB stored + operations | $5-20 |
| **Redis (Cloud Memorystore)** | Instance size | $30-100 |

---

## 6. Environment & Configuration

### Environment Variables

The application behavior is controlled by environment variables. Here's what each one does:

| Variable | What It Controls | Example Value |
|----------|------------------|---------------|
| `DEPLOYMENT_PROFILE` | `local` for dev, `release` for production | `local` |
| `AUTH_MODE` | `dev` skips auth, `oidc` requires Google login | `oidc` |
| `OIDC_ISSUER` | Google OAuth issuer URL | `https://accounts.google.com` |
| `OIDC_AUDIENCE` | Your OAuth client ID | `your-client-id.apps.googleusercontent.com` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+psycopg://user:pass@host:5432/db` |
| `OPENAI_API_KEY` | Your OpenAI API key | `sk-...` |
| `OPENAI_MODEL` | Model for most agents | `gpt-4o-mini` |
| `OPENAI_MODEL_STRATEGY` | Model for strategic agent | `gpt-3.5-turbo` |
| `CORS_ORIGINS` | Allowed frontend origins | `http://localhost:5173` |
| `PREFECT_DEFAULT_DEPLOYMENT_ID` | Prefect deployment for runs | `uuid-here` |
| `CHAT_UPLOAD_DIR` | Where uploaded files are stored | `./.chat_uploads` |
| `CHAT_UPLOAD_MAX_MB` | Max file upload size | `50` |

### Environments

**Development (`DEPLOYMENT_PROFILE=local`)**

- Auth is bypassed (`AUTH_MODE=dev` accepts any bearer token)
- Database runs locally via Docker Compose
- Frontend runs on Vite dev server with hot reload
- Prefect runs locally or connects to Prefect Cloud

**Production (`DEPLOYMENT_PROFILE=release`)**

- Full OIDC authentication required
- Database is Cloud SQL (PostgreSQL)
- Frontend is built static files served from Cloud Run
- Prefect Cloud handles orchestration

### Configuration Files

- **`platform_api/core/config.py`**: Defines all settings and their defaults
- **`.env`**: Local environment variables (never commit this!)
- **`.env.example`**: Template showing required variables
- **`docker-compose.yml`**: Local development stack definition

### Secrets Management

**In Development**: Secrets go in `.env` file (gitignored)

**In Production**: Secrets stored in Google Secret Manager, mounted as environment variables in Cloud Run

**Never commit**: API keys, database passwords, OAuth secrets

---

## 7. Lessons Learned — The War Stories

### Bugs & Fixes

**The Dual Orchestration Path Problem**

*What happened:* The system had two ways to start a workflow run: `/v1/runs` and `/v1/prefect/hello-runs`. They behaved differently — one created fake run IDs, the other created real Prefect runs. This caused confusion and inconsistent behavior.

*Root cause:* Organic growth without clear ownership. Two developers added two endpoints for similar purposes at different times.

*The fix:* ADR-0001 declared `/v1/runs` as the single canonical path. The Prefect endpoint was deprecated and will be removed.

*Lesson:* When you have two ways to do something, pick one. Document the decision with an ADR (Architecture Decision Record).

**The Tenant Isolation Gap**

*What happened:* During a security review, we found that while the API checked tenant membership, a clever SQL query could potentially access another tenant's data if you knew their IDs.

*Root cause:* Application-level security without database-level enforcement.

*The fix:* Migration 0008 added Row-Level Security (RLS) policies to PostgreSQL. Now even if the API has a bug, the database rejects cross-tenant queries.

*Lesson:* Defense in depth. Don't rely on a single layer of security.

**The Chat Message Durability Problem**

*What happened:* If the server crashed mid-stream, the user's message was lost. They'd have to retype their question.

*Root cause:* Messages were only saved after the full response was generated.

*The fix:* The streaming endpoint now saves the user message immediately, creates a pending assistant message, and updates it as the stream progresses. If the server crashes, the user can see their message and retry.

*Lesson:* For user-generated content, persist early. Don't wait for processing to complete.

### Pitfalls & Landmines

**Middleware Order Matters**

The order middleware is registered in FastAPI is the *reverse* of the order requests are processed. We spent a day debugging why rate limiting wasn't working, only to discover it was registered after CORS middleware, so CORS preflight requests bypassed it.

*If you ever need to add middleware*, read the comment in `main.py` carefully. The order is documented there.

**Agent Imports Are Heavy**

Importing an agent module loads all its dependencies (pandas, sklearn, etc.). The `ChatWorkspace` uses lazy imports — agents are only loaded when needed. This keeps startup fast and memory usage reasonable.

*If you add a new agent*, use lazy imports in the dispatch method, not top-level imports.

**Database Migrations in Production**

Running `alembic upgrade head` in production without a backup once caused a 30-minute outage when a migration failed mid-way.

*Always*: 1) Backup the database, 2) Test the migration on a staging copy, 3) Run during low-traffic windows, 4) Have a rollback plan.

**CORS and Credentials**

Setting `allow_credentials=True` in CORS requires specific `allow_origins` — you can't use `*`. This tripped us up when trying to support multiple frontend environments.

*The fix*: Explicitly list allowed origins in `CORS_ORIGINS` environment variable.

### Discoveries

**LangGraph vs. Raw LangChain**

Initially, we used raw LangChain for agent coordination. It worked but was hard to debug — state was scattered, and tracing a request through multiple agents required reading logs carefully.

Switching to LangGraph gave us visual debugging (see the graph of agent interactions) and centralized state management. The learning curve was worth it.

**Prefect Cloud vs. Self-Hosted**

We started with self-hosted Prefect, which required running a PostgreSQL database, a server, and workers. It was operational overhead we didn't need.

Switching to Prefect Cloud removed the operational burden. The free tier handles our current scale, and we can self-host later if needed.

**React Flow for Workflow Designer**

We considered building a custom workflow designer from scratch. React Flow saved weeks of development — it handles drag-and-drop, connections, minimap, and zoom out of the box.

The trade-off: customizing node appearance required understanding React Flow's node rendering system, which has its own learning curve.

### Engineering Wisdom

**Document Decisions with ADRs**

Every significant architectural decision should have an Architecture Decision Record (ADR). These live in `docs/adr/`. They capture: what was decided, why, what alternatives were considered, and what would trigger a re-evaluation.

This has saved us multiple times when someone asked "why did we do it this way?" — the answer is in the ADR.

**Test Contracts, Not Implementation**

Our tests focus on API contracts: given this request, expect this response. We don't test internal implementation details. This makes tests resilient to refactoring.

**Graceful Degradation**

When external services fail, the platform should degrade gracefully, not crash. OpenAI timeout? Show an error and let the user retry. Prefect down? Queue locally. Redis unavailable? Skip caching.

**Structured Logging**

Every log entry has a consistent JSON structure with fields like `tenant_id`, `workspace_id`, `user_id`, `request_id`. This makes debugging production issues much easier — you can filter logs by any field.

---

## 8. Quick Reference Card

### Running the Project Locally

**Prerequisites:**
- Python 3.10+
- Node.js 18+
- Docker Desktop (for PostgreSQL)

**Backend:**

```bash
# Navigate to backend
cd ai-data-science-team/apps/platform-api-app

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your values

# Start PostgreSQL (Docker)
docker compose up -d

# Run migrations
alembic upgrade head

# Start the API
uvicorn platform_api.main:app --reload --port 8000
```

**Frontend:**

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
# Opens at http://localhost:5173
```

**Run Tests:**

```bash
# Backend tests
cd ai-data-science-team/apps/platform-api-app
pytest

# Frontend tests
cd frontend
npm run test
```

### Key URLs

| Environment | URL |
|-------------|-----|
| Local Frontend | http://localhost:5173 |
| Local API | http://localhost:8000 |
| Local API Docs | http://localhost:8000/docs |
| Health Check | http://localhost:8000/healthz |
| Prefect Cloud | https://app.prefect.cloud |

### Common Commands

| Task | Command |
|------|---------|
| Run backend | `uvicorn platform_api.main:app --reload` |
| Run frontend | `npm run dev` |
| Run backend tests | `pytest` |
| Run frontend tests | `npm run test` |
| Create migration | `alembic revision --autogenerate -m "description"` |
| Apply migrations | `alembic upgrade head` |
| Check types (frontend) | `npm run typecheck` |
| Lint code | `npm run lint` (frontend) / `ruff check .` (backend) |

### When Something Breaks

| Problem | Check |
|---------|-------|
| Can't sign in | `AUTH_MODE` setting, Google OAuth config |
| API returns 500 | Check logs for stack trace, verify database connection |
| Chat not streaming | SSE connection, OpenAI API key, rate limits |
| Workflow not running | Prefect deployment ID, worker status |
| Slow responses | OpenAI API latency, database query performance, Redis cache |
| CORS errors | `CORS_ORIGINS` setting, frontend URL |

### Who to Contact

- **Backend issues**: Check `platform_api/` routes and services
- **Frontend issues**: Check `frontend/src/app/screens/` and components
- **Agent issues**: Check `ai_data_science_team/agents/` and `multiagents/`
- **Database issues**: Check `alembic/versions/` for recent migrations
- **Infrastructure issues**: Check `.github/workflows/` and deployment configs

---

*This document was written to make the complex simple. If something is still confusing, that's a bug in the documentation — please ask for clarification.*
