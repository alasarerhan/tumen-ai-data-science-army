# Agentic DS/ML Platform Product Strategy

**Status:** Active product direction and implementation planning input  
**Last updated:** 2026-06-04  
**Scope:** Product direction plus implementation roadmap. The Universal Platform Control Plane foundation, Agent Cockpit summary, richer Agent Cockpit trace metrics, Run Detail trace tab with Trace Inspector, cost/token/evaluation/version trace metadata, artifact previews, first-pass Workflow Run Matrix, Reports Artifact Lineage / Output Board, artifact-backed ModelOps candidates, persisted ModelOps registry/monitor/deployment store, tenant-admin trace cost/token FinOps summary, and local Control Plane CLI/stdio adapters are implemented. Model monitor jobs/alerts, deployment automation beyond metadata handoff, richer graph visualization, external Prefect connectivity, and LLM-assisted planning remain roadmap items unless explicitly marked complete.

## Positioning

AI Data Science Team should be positioned as an agentic data science and ML operations platform, not as a chat-first analytics app.

The core product is the ability to design, run, monitor, debug, and automate data science and machine learning work through typed agent workflows. Chat remains important, but its main role is the product control plane: users ask about workflow status, model performance, failures, drift, cost, schedules, and recommended next actions.

Target statement:

> AI Data Science Team automates the work normally done by data scientists and ML engineers by turning data ingestion, analysis, feature engineering, modeling, deployment, monitoring, and retraining into governed agent workflow graphs that can be observed visually and queried through chat.

## Market Baseline

The market separates into several overlapping product classes:

| Product class | Representative products | Baseline capabilities |
|---|---|---|
| Visual DS/AI platforms | Dataiku, Domino | Flow/graph workspace, datasets, recipes, model build/deploy, monitoring, governance |
| Cloud MLOps platforms | SageMaker, Azure ML, Vertex AI | Pipelines, model registry/deploy, model/data drift monitoring, scheduled jobs, alerts |
| Experiment/model tracking | MLflow, W&B, Neptune, Comet | Experiments, metrics, artifacts, model registry, comparison dashboards |
| Workflow orchestration | Prefect, Airflow, Dagster, Kubeflow Pipelines | DAG/run graph, schedules, retries, logs, task outputs, artifacts, lineage |
| Agent/LLM observability | LangSmith, Langfuse, Arize Phoenix, W&B Weave | Traces, spans, tool calls, token/cost, latency, evaluations, feedback, session replay |

Official references used for planning:

- Dataiku Flow and AI Agents: https://doc.dataiku.com/dss/latest/flow/index.html, https://doc.dataiku.com/dss/latest/agents/index.html
- SageMaker Model Monitor and Pipelines: https://docs.aws.amazon.com/sagemaker/latest/dg/model-monitor.html, https://docs.aws.amazon.com/sagemaker/latest/dg/pipelines.html
- Azure ML model monitoring: https://learn.microsoft.com/en-us/azure/machine-learning/concept-model-monitoring
- Google/Vertex AI model monitoring: https://cloud.google.com/vertex-ai/docs/model-monitoring/overview
- MLflow tracking: https://mlflow.org/docs/latest/ml/tracking/
- Prefect artifacts and automations: https://docs.prefect.io/v3/develop/artifacts, https://docs.prefect.io/v3/concepts/automations
- Airflow UI: https://airflow.apache.org/docs/apache-airflow/stable/ui.html
- Kubeflow Pipelines UI and artifacts: https://www.kubeflow.org/docs/components/pipelines/interfaces/, https://www.kubeflow.org/docs/components/pipelines/user-guides/data-handling/artifacts/
- LangSmith observability: https://docs.langchain.com/langsmith/observability
- Langfuse observability: https://langfuse.com/docs/observability/overview
- Arize Phoenix: https://arize.com/docs/phoenix
- W&B Weave: https://docs.wandb.ai/weave/

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

1. **Typed agent workflow graph**
   - Nodes represent DS/ML agents and platform tasks.
   - Edges carry typed artifacts: dataset, profile, feature set, model, metrics, evaluation report, deployment, monitor signal, retrain candidate, report.
   - Validation is based on agent capability and artifact contracts, not only node order.

2. **Agent execution observability**
   - Every agent run should expose safe, inspectable internals: input, config, tool calls, generated code or query, artifacts, duration, retries, validation results, token/cost, errors.
   - Do not expose raw private reasoning. Show auditable traces and outputs.

3. **Workflow and model operations**
   - Users see workflow DAG status, run heatmaps, artifact lineage, model versions, deployments, drift, and retraining recommendations.
   - The product explains why a run failed, why a workflow slowed down, or why model quality changed.

4. **Chat as control plane**
   - Chat is not backed by a fixed list of supported questions. It maps natural language to catalog-backed platform queries and governed action plans.
   - Chat answers only from authorized platform state, resolver output, provenance, and redaction rules.
   - Chat actions must be permission-aware, auditable, and policy-gated for risky operations.

## Target Visual Surfaces

| Surface | Purpose | Primary users |
|---|---|---|
| Workflow Designer | Build typed agent graphs and schedules | Analysts, data scientists, ML engineers |
| Workflow DAG View | Inspect one workflow structure, node contracts, and status | Analysts, operators |
| Run Detail | Inspect one run with logs, signals, node executions, and artifacts | Operators, data scientists |
| Run Matrix / Heatmap | Compare repeated workflow runs by node, status, duration, retries, and artifact count; first-pass RunsList matrix exists | Operators, managers |
| Agent Cockpit | Inspect each agent's usage, success rate, latency, tool calls, artifact counts, and failure modes; trace-backed metrics exist | ML engineers, platform owners |
| Agent Run Detail | Inspect a single agent execution trace and produced artifacts; Run Detail Trace Inspector exists | ML engineers, support |
| Agent Output Gallery | Browse charts, tables, code, models, reports, evaluations by agent/workflow/run | Analysts, executives |
| Artifact Lineage Graph | See how datasets become features, models, reports, and dashboards; first-pass Reports graph exists | Data scientists, auditors |
| ModelOps View | Track artifact-backed candidates plus persisted model versions, model cards, stages, monitor snapshots, deployment metadata, rollback metadata, drift/performance status, and retrain candidates | ML engineers, operators |
| Automation Center | Define schedule/event rules and approval policies | Operators, admins |
| Chat Control Plane | Ask operational questions and take governed actions | All roles |

## Implementation Roadmap

### Phase 0 - Product truth and terminology

- Reframe docs and UI copy away from "chat app" language.
- Treat AI Workspace as control-plane and exploratory interface, not the product core.
- Keep `/v1/runs` as the stable public execution contract.

### Phase 1 - Observability data model

- Done first-pass: add `agent_execution_traces` storage with safe input/output summaries, tool-call keys, artifact IDs, timing, status, and error summary.
- Done first-pass: token usage, cost summary, evaluation summary, and version metadata are nullable safe trace fields consumed by Agent Cockpit and Run Detail.
- Still open: richer span payloads, session replay, and governed prompt/tool/config version workflows.
- Done first-pass: artifact lineage query support exists through Control Plane relationships and Reports consumes persisted parent artifact IDs.

### Phase 2 - Visual observability screens

- Done first-pass: Agent Cockpit execution summary from existing node executions, richer trace-backed Agent Cockpit metrics, Run Detail Agent Traces tab with selected Trace Inspector, RunsList Workflow Run Matrix from run node execution data, and Reports Artifact Lineage / Output Board from artifact metadata.
- Done first-pass: Agent Cockpit and Agent Run Detail consume cost/token/evaluation/version metadata and rendered artifact preview states.
- Expand Run Detail into node-level trace and output inspection.
- Extend Artifact Lineage with rebuild-impact analysis, bundle explorer, and richer graph interaction.

### Phase 3 - ModelOps lifecycle

- Done first-pass: promote model artifacts into an artifact-backed ModelOps registry.
- Done: persist model version, model card, stage, approval state, deployment metadata, rollback metadata, and monitor snapshots in `model_registry_entries`, `model_deployment_records`, and `model_monitor_snapshots`.
- Done first-pass: expose artifact-backed monitor snapshots, drift/performance status, and retrain candidate records.
- Still open: model monitor jobs for drift, quality, bias, feature attribution, operational health, thresholds, owners, and alerts.

### Phase 4 - Governed automations

- Add event-action automation rules:
  - stuck run -> alert/retry
  - drift threshold -> create approval/retrain candidate
  - failed run rate -> pause schedule
  - cost threshold -> notify owner
- Add approval policies for deploy, retrain, export, destructive data operations, and high-cost runs.

### Phase 5 - Chat control plane

Status: initial foundation implemented on 2026-06-04.

- Completed foundation: independent backend bounded context under `platform_api/control_plane/`, descriptor catalog, query/action DTOs, resolver registry, policy/redaction engine, provenance, `/v1/control-plane/*` routes, chat routing, frontend API client, and generic `platform_query_result` renderer.
- Remaining expansion: model monitor jobs/alerts, live external Prefect connectivity, richer graph visualization, deployment automation beyond metadata handoff, and deeper natural-language planning.
- Guardrail: chat control-plane behavior stays independent from DS/ML agent registry, workflow agent planners, and ChatWorkspace analytical routing.

## Near-Term Backlog

1. Done: fix Workflow Designer new route mismatch (`/workflows/new/designer` vs `/workflows/new`).
2. Done: replace mock YAML/version history in Workflow Detail with real spec serialization and version list.
3. Add ModelOps node types: `model.deploy`, `model.monitor`, `model.explain`, `model.retrain`, `experiment.ab_test`, `dashboard.generate`.
4. Make workflow worker dependency-aware instead of only execution-index ordered.
5. Done: add Agent Cockpit execution summary, trace-backed cockpit metrics, safe trace storage/read contracts, Run Detail Trace Inspector, cost/token/evaluation/version metadata, and artifact previews.
6. Done first-pass: add Run Matrix / Heatmap and Reports Artifact Lineage / Output Board; still open: richer cost-aware matrix data and rebuild-impact/bundle lineage workflows.
7. Done: add artifact-backed ModelOps API/UI plus persisted production registry, monitor, and deployment metadata store; still open: monitor jobs, deployment automation beyond metadata handoff, and alert rules.
8. Done foundation: add Universal Platform Control Plane query/action layer.
9. Done: expand Control Plane to model/monitor/docs/adapter metadata, trace cost/token FinOps summary, local CLI adapter, and local stdio bridge; still open: live external Prefect connectivity and deeper planner coverage.

## Acceptance Gates Before Implementation Is Called Complete

- Each new visual surface has loading, empty, error, permission, and stale-data states.
- Every persisted trace avoids raw private reasoning and secret leakage.
- Chat-triggered actions are RBAC-checked and auditable.
- Model monitoring alerts have owner, threshold, baseline, and remediation path.
- Workflow and model state can be explained from data, not mock UI state.
- Release docs distinguish implemented capability from planned roadmap.
