# Platform Strategy

> Consolidated strategy and roadmap.
> Replaces the legacy Turkish-language root `STRATEGY.md` (kept for historical context only) and the English-language `docs/product-strategy-agentic-dsml-platform.md`.

**Status:** Active product direction and implementation planning input.
**Last updated:** 2026-06-04.

## Positioning

AI Data Science Team is positioned as an **agentic data science and ML operations platform**, not a chat-first analytics app.

The core product is the ability to design, run, monitor, debug, and automate data science and machine learning work through typed agent workflows. Chat remains important, but its main role is the product control plane: users ask about workflow status, model performance, failures, drift, cost, schedules, and recommended next actions.

**Target statement:**

> AI Data Science Team automates the work normally done by data scientists and ML engineers by turning data ingestion, analysis, feature engineering, modeling, deployment, monitoring, and retraining into governed agent workflow graphs that can be observed visually and queried through chat.

## Market Baseline

| Product class | Representative products | Baseline capabilities |
|---|---|---|
| Visual DS/AI platforms | Dataiku, Domino | Flow/graph workspace, datasets, recipes, model build/deploy, monitoring, governance |
| Cloud MLOps platforms | SageMaker, Azure ML, Vertex AI | Pipelines, model registry/deploy, model/data drift monitoring, scheduled jobs, alerts |
| Experiment/model tracking | MLflow, W&B, Neptune, Comet | Experiments, metrics, artifacts, model registry, comparison dashboards |
| Workflow orchestration | Prefect, Airflow, Dagster, Kubeflow Pipelines | DAG/run graph, schedules, retries, logs, task outputs, artifacts, lineage |
| Agent/LLM observability | LangSmith, Langfuse, Arize Phoenix, W&B Weave | Traces, spans, tool calls, token/cost, latency, evaluations, feedback, session replay |

## Product Baseline Gaps

The repository already has workflow design, runs, artifacts, signals, SQL Server data sources, settings, and an agent catalog. The following market-baseline capabilities are not yet product-complete.

| Capability | Current repo signal | Gap |
|---|---|---|
| Model registry | Model artifacts, MLflow-related agent code, `/v1/modelops/summary`, `/modelops`, and Control Plane `modelops` exist | First-pass registry is artifact-backed; durable registry store, model cards, champion/challenger, and approval workflow remain open |
| Model serving | `ModelServingAgent` is in the production agent catalog | No workflow node, deployment endpoint, serving health view, inference log view, or rollback path |
| Model monitoring | `ModelMonitoringAgent`, anomaly/drift capabilities, artifact-backed monitor snapshots, drift/performance status, and ModelOps dashboard exist | Baseline dataset store, scheduled drift jobs, quality monitor thresholds, and alert routing remain open |
| Closed-loop retraining | Workflow scheduling, run retry, and artifact-backed retrain candidate detection exist | Governed trigger path from drift/performance degradation to retrain/evaluate/approve/deploy workflow remains open |
| Feature registry | Feature engineering node and artifact type exist | No reusable feature definitions, freshness checks, offline/online parity, or feature lineage screen |
| Experiment tracking | H2O/MLflow support exists in agent library | No product screen for experiment comparison, metric leaderboard, or run-to-model lineage |
| Agent observability | Agent registry, run nodes, logs, artifacts, safe `agent_execution_traces` storage/read contracts, Agent Cockpit metrics from `run.nodes` + `agent.traces`, cost/token/evaluation/version trace fields, and Run Detail Trace Inspector with artifact previews exist | Full span timeline, session replay, prompt/tool/config governance workflow, and richer artifact previews remain open |
| Agent/version governance | Agent metadata exists | No prompt/tool/config versioning, evaluator set tracking, agent release approval, or agent rollback |
| Event automations | Schedule/pause/resume and signals exist | No event-action rules such as stuck-run retry, drift-triggered approval, or cost threshold notification |
| Artifact lineage UI | Parent artifact IDs are stored; Reports has a first-pass Artifact Lineage Graph from safe artifact metadata | No rebuild impact view, artifact bundle explorer, or richer graph interaction beyond the first-pass Reports view |
| Dashboard/report builder | Reports and chart artifacts exist; Reports has a first-pass Pipeline Output Board grouped by artifact type | No dashboard builder, recurring report scheduler, KPI monitor, or governed share/export flow |
| Collaboration/review | Workflow status/version fields and real Workflow Detail version list exist; restore/diff are disabled until backend contracts exist | No real workflow diff, comments, review queue, restore, or audit package view |
| Chat control plane | Universal Platform Control Plane now exposes catalog-backed query/action APIs, `platform_query_result` artifacts, DB-backed scheduler metadata, tenant-admin FinOps summary with trace cost/tokens, persisted ModelOps store plus artifact-backed fallback, docs task counts/search snippets, local CLI/stdio adapter metadata, and artifact lineage relationships | Coverage still needs live external Prefect connectivity, richer graph visualization, LLM planner, and deeper governed action coverage |

## Differentiation

The target differentiation is not to clone a single MLOps or workflow tool. The differentiated product combines four planes:

1. **Typed agent workflow graph** — Nodes represent DS/ML agents and platform tasks. Edges carry typed artifacts: dataset, profile, feature set, model, metrics, evaluation report, deployment, monitor signal, retrain candidate, report. Validation is based on agent capability and artifact contracts, not only node order.
2. **Agent execution observability** — Every agent run exposes safe, inspectable internals: input, config, tool calls, generated code or query, artifacts, duration, retries, validation results, token/cost, errors. No raw private reasoning.
3. **Workflow and model operations** — Users see workflow DAG status, run heatmaps, artifact lineage, model versions, deployments, drift, retraining recommendations.
4. **Chat as control plane** — Chat maps natural language to catalog-backed platform queries and governed action plans. Answers only from authorized platform state, resolver output, provenance, and redaction rules. Actions are permission-aware, auditable, and policy-gated.

## Operating Modes (from legacy strategy)

The platform is designed to operate in four modes to serve different user needs:

1. **Fully Autonomous Mode** — User sets a business goal. Platform runs the entire process end-to-end.
2. **Optional Intervention Mode (Human-in-the-Loop)** — Pipeline never blocks waiting for the user. `WorkflowSignal` lets users observe, intervene, or annotate at any time. Notifications are sent only when all automatic recovery (retry + backoff, fallback, circuit breaker) is exhausted.
3. **Human-Designed, Autonomous Execution Mode** — User designs/saves the workflow; it is scheduled or triggered by event.
4. **Conversational Analysis Mode (AI Workspace)** — User asks natural-language questions or uploads data; the platform selects the appropriate agent and streams analysis/predictions/reports. No workflow design or coding required.

## Architectural Principles

- **Decoupled Architecture** — Frontend (React) and Backend (FastAPI) layers are separated and communicate through API contracts.
- **Hybrid Orchestration** — Interactive (chat/UX) uses LangGraph supervisor + existing agent/tool ecosystem; production runs (schedule/retry/history) use Prefect (Prefect Cloud).
- **Multi-Tenant Security** — Isolation enforced at backend, not just UI.
- **Artifact Access Policy** — Artifacts accessed through backend (signed URL / stream); direct bucket access is not assumed.
- **Operational Discipline** — Structured logging, audit logging, rate limit / quotas, secrets management, migration, and rollback.
- **On-Prem Priority** — Initial deployment on-prem via Docker Compose-first; Kubernetes (Helm) in a later phase.

## Target Platform Components

- **Frontend** — React (enterprise UX + RBAC visibility + workflow designer surface + AI Workspace conversation interface).
- **Backend API** — FastAPI (auth, tenancy, metadata, orchestration gateway).
- **Orchestrator** — Prefect Cloud (schedule, retries, queue/worker, run history) + LangGraph (supervisor-led interactive routing and tool invocations).
- **Metadata Store** — PostgreSQL (Cloud SQL) — tenant/workspace/user/RBAC, workflow definitions, run records, audit log.
- **Artifact Store** — GCS (single bucket + tenant/workspace prefix). Backend-only access.
- **Secrets** — GCP Secret Manager (cloud). On-prem: equivalent via env/secrets file (compose).
- **Runtime** — Cloud: GCP Cloud Run (API and worker services as needed). On-prem: Docker Compose.

## Multi-Tenant and Concurrency Principles

- **Tenant** — Enterprise customer boundary. Each user is a member of one or more tenants.
- **Workspace** — Project/working area within a tenant. Data sources, workflows, and runs are scoped to a workspace.
- **Isolation** — Every API call is validated with tenant/workspace context. All DB records are scoped; unauthorized access is blocked at backend. Prefect uses workspace-per-tenant (or tag/queue separation) for tenant isolation.
- **Provisioning** — Admin-created / invite-only (no self-serve sign-up).
- **Audit + Quotas** — All critical operations (invite, workflow run, artifact access, secrets) write to audit log; tenant-level rate limits / quotas enforced.

## Implementation Roadmap

### Phase 0 — Product truth and terminology
- Reframe docs and UI copy away from "chat app" language.
- Treat AI Workspace as control-plane and exploratory interface, not the product core.
- Keep `/v1/runs` as the stable public execution contract.

### Phase 1 — Observability data model
- Done first-pass: `agent_execution_traces` storage with safe input/output summaries, tool-call keys, artifact IDs, timing, status, error summary.
- Done first-pass: token usage, cost summary, evaluation summary, version metadata as nullable safe trace fields.
- Still open: richer span payloads, session replay, governed prompt/tool/config version workflows.
- Done first-pass: artifact lineage query support through Control Plane relationships and Reports consumes persisted parent artifact IDs.

### Phase 2 — Visual observability screens
- Done first-pass: Agent Cockpit execution summary, trace-backed Agent Cockpit metrics, Run Detail Agent Traces tab with Trace Inspector, RunsList Workflow Run Matrix, Reports Artifact Lineage / Output Board.
- Done first-pass: Agent Cockpit and Run Detail consume cost/token/evaluation/version metadata and rendered artifact preview states.
- Expand Run Detail into node-level trace and output inspection.
- Extend Artifact Lineage with rebuild-impact analysis, bundle explorer, richer graph interaction.

### Phase 3 — ModelOps lifecycle
- Done first-pass: promote model artifacts into an artifact-backed ModelOps registry.
- Done: persist model version, model card, stage, approval state, deployment metadata, rollback metadata, monitor snapshots in `model_registry_entries`, `model_deployment_records`, `model_monitor_snapshots`.
- Done first-pass: expose artifact-backed monitor snapshots, drift/performance status, retrain candidate records.
- Still open: model monitor jobs for drift, quality, bias, feature attribution, operational health, thresholds, owners, alerts.

### Phase 4 — Governed automations
- Event-action automation rules:
  - stuck run → alert/retry
  - drift threshold → create approval/retrain candidate
  - failed run rate → pause schedule
  - cost threshold → notify owner
- Approval policies for deploy, retrain, export, destructive data operations, high-cost runs.

### Phase 5 — Chat control plane (M22)
Status: initial foundation implemented on 2026-06-04.

- Completed foundation: `platform_api/control_plane/` bounded context, descriptor catalog, query/action DTOs, resolver registry, policy/redaction engine, provenance, `/v1/control-plane/*` routes, chat routing, frontend API client, generic `platform_query_result` renderer.
- Remaining expansion: live external Prefect connectivity, richer graph visualization, deployment automation beyond metadata handoff, deeper natural-language planning.
- Guardrail: chat control-plane behavior stays independent from DS/ML agent registry, workflow agent planners, and ChatWorkspace analytical routing.

See `docs/M22-RUNTIME.md` for the M22 lifecycle parity matrix and command evidence.

## Near-Term Backlog

1. Done: fix Workflow Designer new route mismatch (`/workflows/new/designer` vs `/workflows/new`).
2. Done: replace mock YAML/version history in Workflow Detail with real spec serialization and version list.
3. Add ModelOps node types: `model.deploy`, `model.monitor`, `model.explain`, `model.retrain`, `experiment.ab_test`, `dashboard.generate`.
4. Make workflow worker dependency-aware instead of only execution-index ordered.
5. Done: add Agent Cockpit execution summary, trace-backed cockpit metrics, safe trace storage/read contracts, Run Detail Trace Inspector, cost/token/evaluation/version metadata, artifact previews.
6. Done first-pass: add Run Matrix / Heatmap and Reports Artifact Lineage / Output Board; still open: richer cost-aware matrix data and rebuild-impact/bundle lineage workflows.
7. Done: add artifact-backed ModelOps API/UI plus persisted production registry, monitor, and deployment metadata store; still open: monitor jobs, deployment automation beyond metadata handoff, alert rules.
8. Done foundation: add Universal Platform Control Plane query/action layer.
9. Done: expand Control Plane to model/monitor/docs/adapter metadata, trace cost/token FinOps summary, local CLI adapter, local stdio bridge; still open: live external Prefect connectivity, deeper planner coverage.

## Locked Decisions (from legacy Turkish strategy)

- **Orchestration**: Prefect Cloud (production runs) + LangGraph (interactive supervisor).
- **Cloud**: GCP priority; runtime Cloud Run.
- **On-Prem**: Docker Compose-first.
- **Frontend**: React.
- **Authentication**: OIDC (Google Workspace).
- **Metadata Store**: Cloud SQL (Postgres).
- **Artifacts**: GCS, tenant/workspace prefix; backend-only access (signed URL / stream).
- **Secrets**: GCP Secret Manager.
- **Provisioning**: Admin-created / invite-only.
- **HITL (Human-in-the-Loop)**: Optional intervention via `WorkflowSignal` — pipeline never blocks; runtime user can engage at any time.
- **Orchestration Layer (M22)**: AgentRegistry + ContextStore + WorkflowResolver + RuntimeEngine + WorkflowSignal + OrchestratorAgent — supports 3 scenarios (dynamic, supervised, fully manual).

## Acceptance Gates

- Each new visual surface has loading, empty, error, permission, and stale-data states.
- Every persisted trace avoids raw private reasoning and secret leakage.
- Chat-triggered actions are RBAC-checked and auditable.
- Model monitoring alerts have owner, threshold, baseline, and remediation path.
- Workflow and model state can be explained from data, not mock UI state.
- Release docs distinguish implemented capability from planned roadmap.

## Execution Status (2026-06-04)

Implemented surface (first-pass or complete, per scope statements above):
- Universal Platform Control Plane foundation
- Agent Cockpit summary + trace-backed metrics
- Run Detail Trace Inspector with cost/token/evaluation/version/artifact previews
- Workflow Run Matrix
- Reports Artifact Lineage / Output Board
- Artifact-backed ModelOps candidates
- Persisted ModelOps registry/monitor/deployment store
- Tenant-admin trace cost/token FinOps summary
- Local Control Plane CLI/stdio adapters

Roadmap (still open unless explicitly marked complete):
- Model monitor jobs/alerts
- Deployment automation beyond metadata handoff
- Richer graph visualization
- External Prefect connectivity
- LLM-assisted planning

---

**Source consolidation note**

- Legacy `STRATEGY.md` (Turkish, 2026-03-04, v1.4) → §Operating Modes, §Architectural Principles, §Multi-Tenant Principles, §Locked Decisions, §Execution Status. The legacy file is kept at repo root for historical reference; this `docs/STRATEGY.md` is canonical.
- `docs/product-strategy-agentic-dsml-platform.md` (English, 2026-06-04) → §Positioning, §Market Baseline, §Product Baseline Gaps, §Differentiation, §Target Components, §Implementation Roadmap, §Near-Term Backlog, §Acceptance Gates.
