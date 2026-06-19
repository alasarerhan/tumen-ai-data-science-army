# Chain Validator Rules

This document summarizes the machine-enforced workflow chain rules.

Source of truth:
- Frontend/UI rules: [agentChainRules.json](../../frontend/src/app/config/agentChainRules.json)
- Frontend validator: [workflowChainValidator.ts](../../frontend/src/app/utils/workflowChainValidator.ts)
- Backend validator: [workflow_chain_validator.py](../apps/platform-api-app/platform_api/services/workflow_chain_validator.py)

## Validator Outcomes

| Outcome | Meaning | Runtime behavior |
|---|---|---|
| `ok` | Safe structural chain | Allowed with no issue |
| `warning` | Conditional or advisory chain | Allowed, but shown as warning |
| `error` | Blocked chain | Rejected |

## High-Signal Rules

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

## Design Intent

The validator is intentionally permissive for advisory/report-driven flows:
- `EDA -> Cleaning` is allowed with warning
- `DataQuality -> Cleaning` is allowed with warning
- `AnomalyDetection -> Cleaning` is allowed with warning

The validator is intentionally strict for typed artifact mismatches:
- `Visualization -> H2O ML` is rejected
- `ModelEvaluation -> H2O ML` is rejected
- `MLflowTools -> Wrangling/Cleaning/Feature/H2O ML` is rejected
