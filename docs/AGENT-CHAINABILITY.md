# Agent Chainability Reference

> Machine-enforced chain rules and the structural/contract map of the agent set.
> Replaces `planning_docs/chain_validator_rules.md` and `planning_docs/agent_chainability_matrix.md`.

## Sources of Truth

- Frontend UI rules: `frontend/src/app/config/agentChainRules.json`
- Frontend validator: `frontend/src/app/utils/workflowChainValidator.ts`
- Backend validator: `apps/platform-api-app/platform_api/services/workflow_chain_validator.py`
- Supervisor state: `ai_data_science_team/multiagents/supervisor/state.py`
- Active dataset resolution: `ai_data_science_team/multiagents/supervisor/datasets.py`
- Supervisor nodes: `ai_data_science_team/multiagents/supervisor_ds_team.py`

## Validator Outcomes

| Outcome | Meaning | Runtime behavior |
|---|---|---|
| `ok` | Safe structural chain | Allowed with no issue |
| `warning` | Conditional or advisory chain | Allowed, but shown as warning |
| `error` | Blocked chain | Rejected |

## Decision Rules

| Rule | Meaning |
|---|---|
| Safe | Output of agent A already matches input contract of agent B, or the supervisor already wires this pair directly. |
| Conditional | The pair can work, but only with extra mapping, extra parameters, advisory context, or modality/schema constraints. |
| No | The output modality of agent A does not satisfy the input contract of agent B, so direct chaining is misleading or wrong. |

Important distinction:

- **Structural chain**: upstream produces a typed artifact that the downstream reads as a first-class input.
- **Advisory chain**: upstream does not transform the dataset, but its report can still influence the downstream through message history or human review.

## High-Signal Rules (Source × Safe / Conditional / Blocked Next)

| Source agent | Safe next | Conditional next | Blocked examples |
|---|---|---|---|
| DataLoaderToolsAgent | Wrangling, Cleaning, EDA, Visualization, Feature, Quality, Anomaly | H2O ML, Time Series agents | Narrative, MLflow, Model Explainability |
| SQLDatabaseAgent | Wrangling, Cleaning, EDA, Visualization, Feature, Quality, Anomaly | H2O ML, Time Series agents | Narrative, Model Serving |
| DataWranglingAgent | Cleaning, EDA, Visualization, Feature, Quality, Anomaly | H2O ML, Time Series agents | Model Serving, Model Explainability |
| DataCleaningAgent | EDA, Visualization, Feature, Quality, Anomaly | H2O ML, Time Series agents | Model Serving, Model Explainability |
| EDAToolsAgent | ResultsSynthesizer, Narrative, Recommendation, ContextualKnowledge | Cleaning, Feature, H2O ML, Quality, Anomaly, ApprovalGate | Visualization to model is still blocked if used as typed handoff |
| DataVisualizationAgent | ResultsSynthesizer, Narrative, Recommendation | ApprovalGate, MLflow | H2O ML, Cleaning, Feature |
| FeatureEngineeringAgent | H2O ML, EDA, Visualization, Quality, Anomaly | ModelEvaluation, TimeSeriesEDA | Narrative as direct typed consumer |
| H2OMLAgent | ModelEvaluation, MLflowTools | ModelServing, Monitoring, Explainability, EDA, Visualization | Cleaning, Wrangling |
| ModelEvaluationAgent | ResultsSynthesizer, Narrative, Recommendation, MLflowTools, ApprovalGate | None | H2O ML |
| DataQualityAgent | ResultsSynthesizer, Narrative, Recommendation | Cleaning, Feature, H2O ML, ApprovalGate | Visualization as typed row consumer |
| AnomalyDetectionAgent | ResultsSynthesizer, Narrative, Recommendation | Cleaning, Visualization, ApprovalGate | H2O ML |
| APIConnectorAgent | None | Dataset-oriented agents after normalization | Direct strategic/model-ops chains |
| DocumentParserAgent | None | Dataset-oriented agents after table extraction | Direct model/report chains from raw text |
| ModelServingAgent | None | Monitoring, EDA, Visualization, ResultsSynthesizer | Cleaning, Feature, H2O ML |
| ModelMonitoringAgent | ResultsSynthesizer, Narrative, Recommendation, ApprovalGate, MLflowTools | None | Unary single-input assumptions |
| ModelExplainabilityAgent | ResultsSynthesizer, Narrative, Recommendation, ApprovalGate, MLflowTools | None | Raw dataframe transformers |
| TimeSeriesEDAAgent | ResultsSynthesizer, Narrative, Recommendation | ForecastingModel, ForecastEvaluation | Generic tabular H2O path by default |
| ForecastingModelAgent | ForecastEvaluation, Narrative, Recommendation, MLflowTools | None | Generic tabular evaluation |
| ForecastEvaluationAgent | ResultsSynthesizer, Narrative, Recommendation, ApprovalGate, MLflowTools | None | Generic tabular downstream |
| WorkflowPlannerAgent | ApprovalGate, Orchestrator | None | Data transformers as direct consumers |
| ApprovalGateAgent | Orchestrator | WorkflowPlanner | Data transformers as direct consumers |
| OrchestratorAgent | None | None | Treated as worker node |

## Node-Level Requirements

| Agent | Requirement | Validator behavior |
|---|---|---|
| H2OMLAgent | `target_variable` expected | Warning if missing |
| ModelEvaluationAgent | `target_variable` expected | Warning if missing |
| ModelMonitoringAgent | at least 2 inbound edges expected | Warning if missing |
| ModelExplainabilityAgent | at least 2 inbound edges expected | Warning if missing |
| ModelServingAgent | at least 2 inbound edges expected | Warning if missing |

## Production-Safe Supervisor Chain (with state handoff)

| From | Output slot | To | Input expectation | Status | Notes |
|---|---|---|---|---|---|
| Data Loader | `data_raw` | Data Wrangling | `data_raw` dataframe-like | Safe | Loader activates the loaded dataset and resets downstream artifacts. |
| Data Loader | `data_raw` | Data Cleaning | `data_raw` dataframe-like | Safe | Cleaning reads active dataset, which becomes the loaded dataset. |
| Data Loader | `data_raw` | EDA | `data_raw` dataframe-like | Safe | EDA is read-only. |
| Data Loader | `data_raw` | Visualization | `data_raw` dataframe-like | Safe | Visualization is read-only. |
| Data Loader | `data_raw` | Feature Engineering | `data_raw` dataframe-like | Safe | Feature requests still need a sensible target if supervised encoding is intended. |
| Data Loader | `data_raw` | H2O ML | `data_raw` + `target_variable` | Conditional | Training works only if target is set. |
| SQL Database | `data_sql` | Wrangling / Cleaning / EDA / Visualization / Feature / H2O ML | dataframe-like | Safe / Conditional | Modeling remains conditional on target. |
| Data Merge | `data_wrangled` | Cleaning | dataframe-like | Safe | Merge output is registered as active wrangled dataset. |
| Data Merge | `data_wrangled` | EDA / Visualization / Feature / H2O ML | dataframe-like | Safe / Conditional | Modeling still depends on target. |
| Data Wrangling | `data_wrangled` | Cleaning | dataframe-like | Safe | Explicitly covered by deterministic handoff tests. |
| Data Wrangling | `data_wrangled` | EDA / Visualization / Feature / H2O ML | dataframe-like | Safe / Conditional | Modeling still depends on target. |
| Data Cleaning | `data_cleaned` | EDA | dataframe-like | Safe | EDA reads cleaned data first. |
| Data Cleaning | `data_cleaned` | Visualization | dataframe-like | Safe | Visualization reads cleaned data first. |
| Data Cleaning | `data_cleaned` | Feature Engineering | dataframe-like | Safe | Explicitly covered by deterministic handoff tests. |
| Data Cleaning | `data_cleaned` | H2O ML | dataframe-like + `target_variable` | Conditional | H2O can read cleaned data directly. |
| Feature Engineering | `feature_data` | H2O ML | dataframe-like + `target_variable` | Safe | Explicitly covered by deterministic handoff tests. |
| Feature Engineering | `feature_data` | EDA / Visualization | dataframe-like | Conditional | EDA prefers `feature_data` only when user explicitly asks for feature-engineered data. |
| H2O ML | `model_info` + H2O artifacts | Model Evaluation | trained model + dataset + `target_variable` | Safe | Supervisor pulls H2O artifacts into evaluation. |
| H2O ML | MLflow run/model URI | MLflow Log / MLflow Tools | run metadata | Safe | Supervisor has explicit logging and inspection nodes. |
| H2O ML scoring mode | `data_wrangled` predictions dataset | EDA / Visualization | dataframe-like | Safe | H2O registers predictions as a new active dataset. |

## Dataset Precedence in Supervisor

| Agent node | Dataset precedence |
|---|---|
| Wrangling | `data_raw` → `data_sql` → `data_wrangled` → `data_cleaned` → `feature_data` |
| Cleaning | `data_wrangled` → `data_raw` → `data_sql` → `data_cleaned` → `feature_data` |
| EDA | `data_cleaned` → `data_wrangled` → `data_sql` → `data_raw` → `feature_data` |
| Visualization | `data_cleaned` → `data_wrangled` → `data_sql` → `data_raw` → `feature_data` |
| Feature Engineering | `data_cleaned` → `data_wrangled` → `data_sql` → `data_raw` → `feature_data` |
| H2O ML | `feature_data` → `data_cleaned` → `data_wrangled` → `data_sql` → `data_raw` |

Important: `EDA` and `Visualization` do not produce a new dataset slot, so chained downstream data transformers consume the same active dataset the report inspected.

## Advisory Chains

| From | To | Status | Why |
|---|---|---|---|
| EDA | Cleaning | Conditional | EDA summary can inform imputation strategy, outlier handling, type-fix choices. |
| EDA | Feature Engineering | Conditional | EDA findings can guide encoding, binning, interaction design. |
| EDA | H2O ML | Conditional | EDA can influence target framing or modeling direction. |
| Data Quality | Cleaning | Conditional | Quality findings can drive repair decisions. |
| Anomaly Detection | Cleaning | Conditional | Anomaly findings can influence outlier treatment. |
| Visualization | Narrative / Recommendation / ResultsSynthesizer | Conditional | Charts are useful report context, not tabular input. |

## Agent-by-Agent Matrix (Input/Output Contract → Safe / Conditional / Do-Not-Chain)

### Tabular Pipeline Agents

| Agent | Real input contract | Real output contract | Safe next | Conditional next | Do not chain directly |
|---|---|---|---|---|---|
| DataLoaderToolsAgent | message-driven file/directory request | `data_loader_artifacts`, often materialized to `data_raw` | Wrangling, Cleaning, EDA, Visualization, Feature Engineering | H2O ML, Model Evaluation only after target/model prerequisites exist | Strategic agents directly, unless artifacts are first normalized |
| SQLDatabaseAgent | message-driven SQL request + DB connection | `data_sql`, SQL code, SQL function | Wrangling, Cleaning, EDA, Visualization, Feature Engineering | H2O ML with target variable | Model Serving, Monitoring, Explainability directly |
| DataWranglingAgent | `data_raw` dataframe/dict/list | `data_wrangled`, wrangler function | Cleaning, EDA, Visualization, Feature Engineering | H2O ML with target variable | Model Serving, Monitoring, Explainability directly |
| DataCleaningAgent | `data_raw` dataframe | `data_cleaned`, cleaner function | EDA, Visualization, Feature Engineering | H2O ML with target variable | Model Serving, Monitoring, Explainability directly |
| EDAToolsAgent | `data_raw` dataframe | `eda_artifacts` only | ResultsSynthesizer, Narrative, Recommendation, ContextualKnowledge | Cleaning, Feature Engineering, H2O ML as advisory context; ApprovalGate; MLflow log of report artifacts | Treated as row-transform producer |
| DataVisualizationAgent | `data_raw` + instruction | `plotly_graph`, viz function | ResultsSynthesizer, Narrative, Recommendation | ApprovalGate, MLflow logging | Cleaning, Feature Engineering, H2O ML |
| FeatureEngineeringAgent | `data_raw` + optional `target_variable` | `data_engineered` | H2O ML | EDA, Visualization, Model Evaluation | Model Serving, Monitoring, Explainability directly |
| H2OMLAgent | `data_raw` + `target_variable` | `leaderboard`, `best_model_id`, `model_path`, optional MLflow, scoring mode can emit predictions dataset | Model Evaluation, MLflow Log, MLflow Tools | Model Serving, Monitoring, Explainability if model persistence/schema alignment handled | Wrangling/Cleaning directly on model artifacts |
| ModelEvaluationAgent | `data_raw` + `model_artifacts` + `target_variable` | `eval_artifacts`, sometimes `plotly_graph` | ResultsSynthesizer, Narrative, Recommendation | MLflow Log, ApprovalGate | Cleaning, Feature Engineering, H2O ML |
| MLflowToolsAgent | message-driven MLflow task | `mlflow_artifacts` | ResultsSynthesizer, Narrative, Recommendation | Orchestrator or approval/report flows | Data Wrangling, Cleaning, H2O ML as if it emits a dataset |

### Analysis-Only Tabular Agents

| Agent | Real input contract | Real output contract | Safe next | Conditional next | Do not chain directly |
|---|---|---|---|---|---|
| DataQualityAgent | `data_raw` dataframe | `quality_results` | ResultsSynthesizer, Narrative, Recommendation | ApprovalGate, MLflow logging | Cleaning or Feature Engineering as if it emits a cleaned dataset |
| AnomalyDetectionAgent | `data_raw` dataframe | `anomaly_results`, anomaly indices/scores | ResultsSynthesizer, Narrative, Recommendation | Visualization with adapter marking anomalies on rows | Cleaning, Feature Engineering, H2O ML directly |
| ClusteringAgent | `data: list[list[float]]`, `feature_names` | `cluster_artifacts` | ResultsSynthesizer, Narrative, Recommendation | Visualization with adapter | Wrangling/Cleaning/H2O ML directly |

### External Source Bridge Agents

| Agent | Real input contract | Real output contract | Safe next | Conditional next | Do not chain directly |
|---|---|---|---|---|---|
| APIConnectorAgent | URL/method/auth/request config | `api_results`, optional `get_response_as_dataframe()` | Wrangling, Cleaning, EDA, Visualization after converting response to dataframe | Feature Engineering, H2O ML after schema normalization and target definition | Any dataframe-based chain without converting the response body first |
| DocumentParserAgent | `document_source` + parse config | `parse_results`, extracted text, raw tables, `get_tables_as_dataframes()` | EDA, Wrangling, Cleaning after choosing one parsed table | Feature Engineering, H2O ML after table selection and target definition | Direct chaining from raw text output into tabular ML agents |

### Model Ops Agents

| Agent | Real input contract | Real output contract | Safe next | Conditional next | Do not chain directly |
|---|---|---|---|---|---|
| ModelServingAgent | `input_data` + `model_uri` + `task_type` | `serving_results`, predictions, prediction dataframe | DataVisualization, EDA on prediction dataframe if materialized | Monitoring if you also provide reference data and ground truth | Cleaning, Feature Engineering, H2O ML directly from serving result dict |
| ModelMonitoringAgent | `reference_data`, `current_data`, optional `y_true`, `y_pred` | `monitoring_results`, drift/performance reports | ResultsSynthesizer, Narrative, Recommendation | MLflow logging, ApprovalGate | Simple single-input chain from any one upstream agent |
| ModelExplainabilityAgent | `model_artifact`, `background_data`, `explain_data` | `explainability_results`, SHAP/LIME artifacts | ResultsSynthesizer, Narrative, Recommendation | ApprovalGate, MLflow logging | Direct chain from H2O model output unless mapped/exported first |

### Time Series Agents

| Agent | Real input contract | Real output contract | Safe next | Conditional next | Do not chain directly |
|---|---|---|---|---|---|
| TimeSeriesEDAAgent | time-series dataframe + `date_column` + `value_column` | time-series artifacts | Narrative, Recommendation, ResultsSynthesizer | ForecastingModelAgent if same series semantics are maintained | Generic tabular H2O pipeline by default |
| ForecastingModelAgent | time-series dataframe + `date_column` + `value_column` | forecast artifacts/model outputs | ForecastEvaluationAgent | Narrative, Recommendation, MLflow logging | Generic tabular ModelEvaluationAgent without adapter |
| ForecastEvaluationAgent | forecast artifacts + actual series context | evaluation artifacts | Narrative, Recommendation, ResultsSynthesizer | ApprovalGate, MLflow logging | Generic tabular downstream agents |
| AutoForecastAgent | time-series dataframe + date/value columns | combined forecast artifacts | Narrative, Recommendation | ForecastEvaluationAgent if split explicitly | Generic tabular wrangling/cleaning assumptions |

### Strategic, Planning, and Control Agents

| Agent | Real input contract | Real output contract | Safe next | Conditional next | Do not chain directly |
|---|---|---|---|---|---|
| ResultsSynthesizerAgent | `prior_artifacts` dict | strategic artifacts + text | Narrative, Recommendation, ApprovalGate | Orchestrator reporting | Any dataframe/model training agent |
| ContextualKnowledgeAgent | `prior_artifacts` dict | strategic artifacts + text | ResultsSynthesizer, Narrative, Recommendation | ApprovalGate | Any dataframe/model training agent |
| NarrativeAgent | `prior_artifacts` dict | narrative/report artifacts | ApprovalGate | MLflow log as document artifact | Any dataframe/model training agent |
| RecommendationAgent | `prior_artifacts` dict | recommendation artifacts | ApprovalGate | Orchestrator or execution planning | Any dataframe/model training agent |
| WorkflowPlannerAgent | chat history + context | plan JSON: `steps`, `target_variable`, `questions`, `notes` | Supervisor/Orchestrator | ApprovalGate on planned workflow | Dataframe/model agents directly |
| ApprovalGateAgent | `prior_artifacts` + human decision loop | approval artifacts | Any post-approval execution path | Resume flows via thread config | Treating it as a data transformer |
| OrchestratorAgent | `workflow_spec` + user goal | `run_result`, resolved spec, logs | Runtime execution system | Workflow planner, approval, reporting layers | Direct dataframe chaining semantics |

### Composite Multi-Agents

| Agent | Internal chain | Safe usage | Notes |
|---|---|---|---|
| PandasDataAnalyst | Wrangling → Visualization | Safe as a packaged mini-pipeline on raw tabular data | Best treated as a terminal analytic convenience agent, not as a reusable node inside the main supervisor chain. |
| SQLDataAnalyst | SQL → Visualization | Safe as a packaged SQL analytic flow | Same caveat: use as a composite endpoint, not a generic reusable worker in the supervisor chain. |

### CloudOps Agents

| Agent | Real input contract | Real output contract | Chainability |
|---|---|---|---|
| IaCAgent | text instructions | infra artifacts | No meaningful data-science chainability |
| ContainerizationAgent | text instructions | container artifacts | No meaningful data-science chainability |
| CICDAgent | text instructions | CI/CD artifacts | No meaningful data-science chainability |

## Safe Previous Agents (inverse view)

| Agent | Safe previous | Conditional previous | Unsafe previous |
|---|---|---|---|
| DataLoaderToolsAgent | None | WorkflowPlannerAgent, ApprovalGateAgent | Dataset/model/report producers as if loader consumes them |
| SQLDatabaseAgent | None | WorkflowPlannerAgent, ApprovalGateAgent | Dataset/model/report producers as if SQL consumes them |
| DataWranglingAgent | DataLoaderToolsAgent, SQLDatabaseAgent, Data_Merge_Agent, H2O_ML_Agent in scoring mode | APIConnectorAgent, DocumentParserAgent after normalization; EDA/DataQuality as advisory context | Strategic agents, model ops agents |
| DataCleaningAgent | DataLoaderToolsAgent, SQLDatabaseAgent, DataWranglingAgent, Data_Merge_Agent, H2O_ML_Agent in scoring mode | EDA, DataQuality, AnomalyDetection as advisory context; APIConnectorAgent, DocumentParserAgent after normalization | Strategic agents, model ops agents |
| EDAToolsAgent | DataLoaderToolsAgent, SQLDatabaseAgent, DataWranglingAgent, DataCleaningAgent, FeatureEngineeringAgent, Data_Merge_Agent, H2O_ML_Agent in scoring mode | APIConnectorAgent, DocumentParserAgent after normalization | Strategic agents, model ops agents as typed inputs |
| DataVisualizationAgent | DataLoaderToolsAgent, SQLDatabaseAgent, DataWranglingAgent, DataCleaningAgent, FeatureEngineeringAgent, Data_Merge_Agent, H2O_ML_Agent in scoring mode | APIConnectorAgent, DocumentParserAgent after normalization | Strategic agents, model ops agents as typed inputs |
| FeatureEngineeringAgent | DataLoaderToolsAgent, SQLDatabaseAgent, DataCleaningAgent, DataWranglingAgent, Data_Merge_Agent | EDA, DataQuality as advisory context; APIConnectorAgent, DocumentParserAgent after normalization | Strategic agents, model ops agents |
| H2OMLAgent | FeatureEngineeringAgent, DataCleaningAgent, DataWranglingAgent, SQLDatabaseAgent, DataLoaderToolsAgent, Data_Merge_Agent | EDA, DataQuality, RecommendationAgent as advisory context; APIConnectorAgent/DocumentParserAgent after normalization and target setup | Visualization, MLflow Tools, Strategic agents as typed producers |
| ModelEvaluationAgent | H2OMLAgent plus a dataset-producing upstream | EDA or RecommendationAgent as advisory context | Visualization, Strategic agents, MLflow Tools |
| MLflowToolsAgent | H2OMLAgent, ModelEvaluationAgent, MLflow logging flow | ApprovalGateAgent, NarrativeAgent | Dataset transformers as if they emit MLflow runs |
| DataQualityAgent | Any dataset producer | EDA as advisory context | Strategic agents, model ops agents |
| AnomalyDetectionAgent | Any dataset producer | EDA/DataQuality as advisory context | Strategic agents, model ops agents |
| APIConnectorAgent | None | WorkflowPlannerAgent, ApprovalGateAgent | Dataset/model/report producers as if API consumes them |
| DocumentParserAgent | None | WorkflowPlannerAgent, ApprovalGateAgent | Dataset/model/report producers as if parser consumes them |
| ModelServingAgent | H2OMLAgent or external model registry plus an explicit input dataset source | FeatureEngineeringAgent/DataCleaningAgent as the input-data source once model URI exists | EDA, Visualization, Strategic agents as model suppliers |
| ModelMonitoringAgent | ModelServingAgent or external prediction flow plus explicit reference/current datasets | H2OMLAgent if model and comparison datasets are materialized separately | Any simple single-upstream chain pretending monitoring is unary |
| ModelExplainabilityAgent | H2OMLAgent or external model registry plus background/explain datasets | FeatureEngineeringAgent/DataCleaningAgent as the data source once model artifact exists | Strategic/report-only agents |
| TimeSeriesEDAAgent | Time-series dataset producer | WorkflowPlannerAgent | Generic model/report producers |
| ForecastingModelAgent | Time-series dataset producer | TimeSeriesEDAAgent as advisory context | Generic tabular report-only producers |
| ForecastEvaluationAgent | ForecastingModelAgent | TimeSeriesEDAAgent as advisory context | Generic tabular report-only producers |
| AutoForecastAgent | Time-series dataset producer | WorkflowPlannerAgent | Generic report-only producers |
| ResultsSynthesizerAgent | EDA, Visualization, DataQuality, AnomalyDetection, ModelEvaluation, MLflowToolsAgent | H2OMLAgent directly if you want to summarize training artifacts raw | Dataset transformers as if they emit narrative-ready reports automatically |
| ContextualKnowledgeAgent | Any report/artifact producer | WorkflowPlannerAgent | Dataset-only chains without summary context |
| NarrativeAgent | ResultsSynthesizerAgent, EDA, Visualization, ModelEvaluation, RecommendationAgent | H2OMLAgent, DataQualityAgent raw artifacts | Dataset-only chains without artifact selection |
| RecommendationAgent | ResultsSynthesizerAgent, EDA, DataQuality, ModelEvaluation, ContextualKnowledgeAgent | H2OMLAgent raw artifacts | Dataset-only chains without summary context |
| WorkflowPlannerAgent | None | RecommendationAgent, ApprovalGateAgent | Dataset/model/report producers as if planner executes them |
| ApprovalGateAgent | Any artifact/report producer, WorkflowPlannerAgent | H2OMLAgent raw artifacts | Dataset transformers if expecting row output from approval gate |
| OrchestratorAgent | WorkflowPlannerAgent, ApprovalGateAgent | RecommendationAgent | Dataset/model/report producers as if orchestrator is a worker node |

## Explicit Non-Chainable Pairs

These pairings are especially misleading and should be blocked in a UI-level chain builder.

| From | To | Why it should be blocked |
|---|---|---|
| Visualization | Any dataframe/model agent | Visualization emits a graph artifact only. |
| Anomaly Detection | H2O ML | Anomaly report is not a transformed feature matrix. |
| MLflow Tools | Wrangling / Cleaning / Feature / Model | MLflow inspection emits run metadata, not a dataset. |
| Model Evaluation | H2O ML | Evaluation emits metrics, not train-ready data or model state. |
| Narrative / Recommendation / Strategic agents | Any tabular worker | Text/report artifacts are not dataframe inputs. |
| CloudOps agents | Any data science worker | Different domain, no shared contract. |
| Workflow Planner | Data worker directly | Planner emits plan JSON, not data/model artifacts. |
| Orchestrator | Data worker directly | Orchestrator emits run/spec state, not dataset artifacts. |

## UI / Product Guardrails

| Guardrail | Why |
|---|---|
| Only allow direct auto-chain when upstream output type matches downstream required type. | Prevents artifact-to-data mismatches. |
| Separate `dataset`, `model`, `report`, `visualization`, `plan`, `ops` into explicit port types. | Current confusion comes from all agents being treated as if they produce the same thing. |
| Require `target_variable` before enabling `H2O_ML_Agent` and `ModelEvaluationAgent`. | These nodes are invalid without supervision target. |
| Require dual inputs for `ModelMonitoringAgent`. | Monitoring is not a linear single-upstream node. |
| Require explicit adapter nodes for `APIConnectorAgent` and `DocumentParserAgent` before tabular ML chains. | Their raw outputs are not guaranteed to be dataframes. |
| Treat `EDA`, `Visualization`, `DataQuality`, `AnomalyDetection`, and strategic agents as report branches by default. | They are usually side branches, not row-transform branches. |
| Allow report/inspection agents to feed transform/model agents only through an explicit `advisory` or `context` edge type. | Preserves useful guidance without pretending there is a typed dataset handoff. |
| Treat `ModelServingAgent`, `ModelExplainabilityAgent`, and `ModelMonitoringAgent` as model-ops branch nodes. | They depend on model artifacts and/or multiple inputs. |

## Recommended Port Typing

| Port type | Example producers | Example consumers |
|---|---|---|
| `dataset` | Loader, SQL, Merge, Wrangling, Cleaning, Feature Engineering, H2O scoring | Wrangling, Cleaning, EDA, Visualization, Feature Engineering, H2O ML |
| `model_artifact` | H2O ML, external model registry | Model Evaluation, Model Serving, Model Explainability |
| `report_artifact` | EDA, Data Quality, Anomaly, Evaluation, Strategic agents | ResultsSynthesizer, Narrative, Recommendation, ApprovalGate |
| `visualization` | Visualization, Evaluation | Narrative, MLflow logging, UI rendering |
| `plan` | WorkflowPlannerAgent | Orchestrator, supervisor |
| `ops_artifact` | MLflow Tools, CloudOps agents | ApprovalGate, UI rendering, orchestration |

## Design Intent (from validator rules)

The validator is intentionally permissive for advisory/report-driven flows:

- `EDA → Cleaning` is allowed with warning
- `DataQuality → Cleaning` is allowed with warning
- `AnomalyDetection → Cleaning` is allowed with warning

The validator is intentionally strict for typed artifact mismatches:

- `Visualization → H2O ML` is rejected
- `ModelEvaluation → H2O ML` is rejected
- `MLflowTools → Wrangling/Cleaning/Feature/H2O ML` is rejected

## Bottom Line

The current platform already supports one strong linear tabular path:

`Loader/SQL/Merge → Wrangling → Cleaning → Feature Engineering → H2O ML → Evaluation`

Side branches: `EDA`, `Visualization`, `MLflow`, `Strategic reporting`.

Not every agent should be connectable to every other agent:

- Some agents transform rows
- Some agents inspect rows
- Some agents operate on models
- Some agents operate on reports
- Some agents only plan or orchestrate

Any visual chaining UI should validate by port type, not by generic "agent to agent" connectivity.

---

**Source consolidation note**

- `planning_docs/chain_validator_rules.md` → §Sources of Truth, §Validator Outcomes, §High-Signal Rules, §Node-Level Requirements, §Design Intent.
- `planning_docs/agent_chainability_matrix.md` → §Decision Rules, §Production-Safe Supervisor Chain, §Dataset Precedence, §Advisory Chains, §Agent-by-Agent Matrix, §Safe Previous Agents, §Explicit Non-Chainable Pairs, §UI / Product Guardrails, §Recommended Port Typing, §Bottom Line.
