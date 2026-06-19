# Supervisor DS Team

> Design, gaps, and upgrade plan for the LangGraph supervisor-led data science team.
> Replaces `planning_docs/supervisor/supervisor_team_plan.md` and `planning_docs/supervisor/agent_upgrade_plan.md`.

## Goal

Build a LangGraph supervisor-led data science team (message-first, tool-aware) that can route work across core sub-agents (data loading, wrangling/cleaning, EDA/visualization, SQL, feature engineering, ML training/serving) while remaining backward compatible with existing agent APIs.

## Team & Roles (initial)

- `Data_Loader_Tools_Agent` — directory/file discovery and loading (csv/parquet/etc).
- `Data_Wrangling_Agent` — pandas transformations; light cleaning.
- `Data_Cleaning_Agent` — robust cleaning/imputation; user constraints.
- `EDA_Tools_Agent` — describe, missingness, correlation, Sweetviz.
- `Data_Visualization_Agent` — plotly/matplotlib chart generation.
- `SQL_Database_Agent` — SQL generation/execution; returns data + SQL code.
- `Feature_Engineering_Agent` — feature creation for modeling.
- `H2O_ML_Agent` — AutoML training/eval; optional MLflow logging.
- `MLflow_Tools_Agent` — experiment/registry operations (list/search/runs, artifacts, stage transitions, UI status).

## Supervisor Design

- State: `messages: Sequence[BaseMessage]`, `next: str`, plus shared payload slots (`data_raw`, `data_sql`, `chart_json`, `artifacts`, `errors`).
- Routing rules:
  - Default entry: supervisor inspects last human message and chooses a worker.
  - Avoid same worker twice in a row unless explicitly requested.
  - Prefer table-first workflows unless user explicitly asks for charts/models.
  - If data missing, route to Data_Loader; if data needs shaping, to Data_Wrangling/Cleaning; if query needed, to SQL; if summary needed, to EDA/Visualization; if features/models requested, to Feature_Engineering/H2O_ML; if experiment ops requested, to MLflow_Tools.
- Output format: supervisor returns `messages` with appended AI decision trace; sub-agents return their `messages` and artifacts; supervisor aggregates a concise summary.

## Implementation Status

1. ✅ Draft supervisor prompt & router function (JSON route schema; names must match sub-agent nodes). In `supervisor_ds_team.py`.
2. ✅ Wire sub-agents as nodes (use their `invoke_messages` / `ainvoke_messages`).
3. ✅ Define state schema with additive `messages` and optional slots (`data_raw`, `data_sql`, `plotly_graph`, `model_info`, `mlflow_artifacts`).
4. 🔄 Add guardrails: if a sub-agent returns empty data, reroute or respond with guidance; cap recursion. Basic guards via supervisor routing; future: explicit empties.
5. ✅ Logging: minimal progress prints (`* SUPERVISOR`, chosen worker; sub-agent tool logging already exists).
6. ✅ Demo: `temp/30_supervisor_ds_team_demo.py` showing a table request, a chart request, and a quick model run. Demo created; modeling step optional.

## Backward Compatibility

- Keep sub-agents' legacy entrypoints intact; supervisor uses message-first.
- Do not change artifact shapes beyond existing shims (single-tool unwrapping).
- Supervisor outputs should not break existing getters; add a helper to extract the last AI message if needed.

## Open Questions

- Do we include sandboxed code execution for modeling agents by default? (currently opt-in).
- Should we add a lightweight summarizer node to produce a final "answer" after worker responses?
- Memory: use optional `MemorySaver` checkpointer for short-term conversation continuity.

## Notes / Fixes (post-plan)

- Conversation state: `messages` now uses LangGraph's ID-aware message reducer (prevents duplicated history when nodes return full message lists).
- Message-first sub-agent calls: `invoke_messages(...)` for coding-style agents now forwards `user_instructions` (or infers it from the last user message), which fixes generic/incorrect outputs (especially charts/SQL).
- Data correctness: the supervisor tracks an `active_data_key` so downstream agents use the most recently "active" dataset (raw vs SQL vs wrangled/cleaned/features), avoiding stale plots.

## Agent Upgrade Plan (Gap Analysis)

### Objective

Deliver a reliable end-to-end data science workflow in the supervisor-led team: ingest/load → wrangle/clean → EDA → visualization → model training (H2O) → evaluation → MLflow logging/inspection.

### Current State

- Supervisor router + shared state: `ai_data_science_team/multiagents/supervisor_ds_team.py`
- Sub-agents integrated:
  - `Data_Loader_Tools_Agent` (file discovery/loading)
  - `Data_Wrangling_Agent`, `Data_Cleaning_Agent`
  - `EDA_Tools_Agent` (describe/missing/correlation/Sweetviz/D-Tale)
  - `Data_Visualization_Agent` (Plotly codegen + semantic chart validation)
  - `SQL_Database_Agent`
  - `Feature_Engineering_Agent`
  - `H2O_ML_Agent` (AutoML; optional MLflow logging)
  - `MLflow_Tools_Agent` (inspection/UI/registry operations)
- Streamlit UX: `apps/supervisor-ds-team-app/app.py` (chat + "Analysis Details")

### Key Gaps

1. **No explicit workflow plan**
   - Symptom: multi-step prompts can stop early, skip prerequisites, or do steps out of order.
   - Root: supervisor routing is intent/step based, but not a durable plan with step verification and explicit prerequisites.

2. **Problem setup is underspecified**
   - Symptom: modeling requests fail or produce low-quality results without clarity on target/metric/splits/leakage.
   - Root: "target discovery" and "model spec" are not first-class artifacts; H2O agent relies on prompt inference.

3. **Evaluation artifacts are missing/weak**
   - Symptom: users cannot trust or compare models; no consistent confusion matrix/ROC/metrics table/error slices.
   - Root: no dedicated evaluation agent; results are mostly "leaderboard" and ad-hoc summaries.

4. **MLflow is not end-to-end for the workflow**
   - Symptom: "log everything to MLflow" is inconsistent; charts/EDA/datasets are not logged reliably.
   - Root: MLflow tools primarily support inspection/UI/predict; logging tools for params/metrics/tables/figures are missing.

5. **EDA report rendering is incomplete in Streamlit**
   - Symptom: Sweetviz/D-Tale outputs aren't visible/embedded; users can't easily inspect reports.
   - Root: Streamlit UI only renders Plotly JSON and JSON blobs; doesn't handle HTML report artifacts.

### Upgrade Priorities

#### P0 — Must Have (Unblocks true end-to-end workflows)

1. **WorkflowPlannerAgent (new)**
   - Output: a structured plan object with ordered steps, prerequisites, and required inputs.
   - Example steps: `load`, `validate_schema`, `clean`, `eda_summary`, `viz_requests`, `feature_engineering`, `train`, `evaluate`, `log_mlflow`.
   - Supervisor executes steps sequentially and marks completion with deterministic checks (e.g., "data_cleaned exists and non-empty").

2. **ModelEvaluationAgent (new)**
   - Input: trained model artifact + dataset + target + split strategy.
   - Output: standardized artifacts (metrics table, confusion matrix/ROC for classification, residuals for regression, error slices).
   - Ensure evaluation results are used in the final answer and optionally logged to MLflow.

3. **Expand MLflow tooling to support logging (upgrade)**
   - Add tools: `mlflow_log_params`, `mlflow_log_metrics`, `mlflow_log_table`, `mlflow_log_artifact`, `mlflow_set_tags`, `mlflow_log_figure`.
   - Goal: logging can be performed deterministically (tools), not via LLM free-form code.

4. **Supervisor "Workflow Mode" toggle (app + supervisor)**
   - Add a UI toggle: **Proactive workflow mode** (off by default).
   - When on: supervisor is allowed to propose and run the full workflow even if user request is underspecified; it asks for missing inputs (e.g., target column) as needed.

#### P1 — High Value (Quality + reliability improvements)

1. **Dataset registry & selection UX (upgrade)**
   - Maintain a dataset registry in supervisor state: `datasets[{name}] = {data, schema, provenance}` and `active_dataset_id`.
   - Explicitly route "use dataset X" and prevent silent dataset switches.

2. **DataQualityAgent (new, optional but high ROI)**
   - Output: schema/type inference, missingness rules, leakage checks (IDs), cardinality checks, target viability checks.
   - Can gate modeling: "data is not ready for training because …"

3. **EDA report rendering in Streamlit (upgrade)**
   - Detect Sweetviz/D-Tale outputs and render with `st.components.v1.html(...)` or provide download links.
   - Add a dedicated tab in "Analysis Details" for reports.

4. **Better "done-ness" checks (upgrade)**
   - Replace LLM "looks done" with explicit checks per step (data exists, plot type matches request, model metrics present, MLflow run id present).

#### P2 — Nice to Have (Polish + scale)

1. Task queue / long-running job handling — support longer workflows with progress updates and cancellation.
2. Experiment comparison & model registry workflows — "compare last 5 runs", "promote best to staging", "register model", "serve via MLflow".
3. Reproducibility packs — auto-export notebook/script with executed code for each step + metadata.

### Proposed Integration Order (Milestones)

1. **P0.1–P0.2**: WorkflowPlannerAgent + ModelEvaluationAgent wired into supervisor graph.
2. **P0.3**: Add MLflow logging tools and have supervisor log (tables/figures/metrics) deterministically.
3. **P0.4**: Add "Workflow Mode" toggle in Streamlit and supervisor behavior gates.
4. **P1.1–P1.3**: Dataset registry + DataQuality + EDA report rendering.
5. **P1.4–P2**: Hardening and advanced MLflow registry workflows.

### Acceptance Criteria (Definition of Done)

A single prompt like: "Load churn, clean, EDA, plot MonthlyCharges by Churn, train a churn model, evaluate it, and log everything to MLflow"

- executes without message-order issues,
- produces correct chart types,
- returns evaluation artifacts (not just a leaderboard),
- logs a run with metrics + params + at least one table + one figure + model artifact in MLflow.

---

**Source consolidation note**

- `planning_docs/supervisor/supervisor_team_plan.md` → §Goal, §Team & Roles, §Supervisor Design, §Implementation Status, §Backward Compatibility, §Open Questions, §Notes / Fixes.
- `planning_docs/supervisor/agent_upgrade_plan.md` → §Agent Upgrade Plan (objective, current state, key gaps, upgrade priorities P0/P1/P2, milestones, acceptance criteria).
