from __future__ import annotations

import importlib
import logging
from typing import Any

from ai_data_science_team.agent_registry import AgentRegistry

logger = logging.getLogger(__name__)


AGENT_BOOTSTRAP_SPECS: tuple[dict[str, Any], ...] = (
    {
        "name": "DataLoaderToolsAgent",
        "module": "ai_data_science_team.agents.data_loader_tools_agent",
        "class_name": "DataLoaderToolsAgent",
        "description": "Loads files into the workspace and normalizes raw input assets.",
        "capabilities": ["data_loading", "file_ingestion", "tabular_input"],
        "cost_tier": "low",
        "category": "data",
        "tags": ["data", "loader", "ingestion"],
    },
    {
        "name": "SQLDatabaseAgent",
        "module": "ai_data_science_team.agents.sql_database_agent",
        "class_name": "SQLDatabaseAgent",
        "description": "Queries relational sources and returns structured tabular results.",
        "capabilities": ["sql", "database_querying", "structured_data"],
        "cost_tier": "low",
        "category": "data",
        "tags": ["data", "sql", "database"],
    },
    {
        "name": "DataWranglingAgent",
        "module": "ai_data_science_team.agents.data_wrangling_agent",
        "class_name": "DataWranglingAgent",
        "description": "Reshapes datasets and prepares intermediate analytical tables.",
        "capabilities": ["data_wrangling", "reshape", "transformation"],
        "cost_tier": "low",
        "category": "data",
        "tags": ["data", "wrangling", "transformation"],
    },
    {
        "name": "DataCleaningAgent",
        "module": "ai_data_science_team.agents.data_cleaning_agent",
        "class_name": "DataCleaningAgent",
        "description": "Cleans datasets, handles missing values, and fixes schema issues.",
        "capabilities": ["data_cleaning", "imputation", "schema_fixing"],
        "cost_tier": "low",
        "category": "data",
        "tags": ["data", "cleaning", "quality"],
    },
    {
        "name": "EDAToolsAgent",
        "module": "ai_data_science_team.ds_agents.eda_tools_agent",
        "class_name": "EDAToolsAgent",
        "description": "Profiles datasets and produces exploratory analysis outputs.",
        "capabilities": ["eda", "profiling", "descriptive_stats"],
        "cost_tier": "low",
        "category": "analysis",
        "tags": ["analysis", "eda", "profiling"],
    },
    {
        "name": "DataVisualizationAgent",
        "module": "ai_data_science_team.agents.data_visualization_agent",
        "class_name": "DataVisualizationAgent",
        "description": "Builds plots, charts, and other data visualizations.",
        "capabilities": ["visualization", "charting", "plotting"],
        "cost_tier": "low",
        "category": "analysis",
        "tags": ["analysis", "visualization", "charts"],
    },
    {
        "name": "FeatureEngineeringAgent",
        "module": "ai_data_science_team.agents.feature_engineering_agent",
        "class_name": "FeatureEngineeringAgent",
        "description": "Creates model-ready features and derived analytical columns.",
        "capabilities": ["feature_engineering", "feature_selection", "transformation"],
        "cost_tier": "medium",
        "category": "ml",
        "tags": ["ml", "features", "preprocessing"],
    },
    {
        "name": "AnomalyDetectionAgent",
        "module": "ai_data_science_team.agents.anomaly_detection_agent",
        "class_name": "AnomalyDetectionAgent",
        "description": "Detects outliers, drift, and abnormal behavior in data or runs.",
        "capabilities": ["anomaly_detection", "outlier_detection", "monitoring"],
        "cost_tier": "medium",
        "category": "analysis",
        "tags": ["analysis", "anomaly", "monitoring"],
    },
    {
        "name": "DataQualityAgent",
        "module": "ai_data_science_team.agents.data_quality_agent",
        "class_name": "DataQualityAgent",
        "description": "Evaluates data quality, completeness, and validation issues.",
        "capabilities": ["data_quality", "validation", "profiling"],
        "cost_tier": "low",
        "category": "analysis",
        "tags": ["analysis", "quality", "validation"],
    },
    {
        "name": "APIConnectorAgent",
        "module": "ai_data_science_team.agents.api_connector_agent",
        "class_name": "APIConnectorAgent",
        "description": "Connects to HTTP APIs and normalizes external payloads.",
        "capabilities": ["api_ingestion", "http", "external_data"],
        "cost_tier": "medium",
        "category": "data",
        "tags": ["data", "api", "connector"],
    },
    {
        "name": "DocumentParserAgent",
        "module": "ai_data_science_team.agents.document_parser_agent",
        "class_name": "DocumentParserAgent",
        "description": "Extracts structured data from uploaded documents and text assets.",
        "capabilities": ["document_parsing", "ocr", "text_extraction"],
        "cost_tier": "medium",
        "category": "data",
        "tags": ["data", "documents", "parsing"],
    },
    {
        "name": "ModelServingAgent",
        "module": "ai_data_science_team.agents.g3_model_serving_agent",
        "class_name": "ModelServingAgent",
        "description": "Packages model inference behavior for serving and prediction workflows.",
        "capabilities": ["model_serving", "inference", "deployment"],
        "cost_tier": "medium",
        "category": "ops",
        "tags": ["ops", "serving", "inference"],
    },
    {
        "name": "ModelMonitoringAgent",
        "module": "ai_data_science_team.agents.model_monitoring_agent",
        "class_name": "ModelMonitoringAgent",
        "description": "Monitors model quality, drift, and operational health signals.",
        "capabilities": ["model_monitoring", "drift_detection", "alerting"],
        "cost_tier": "medium",
        "category": "ops",
        "tags": ["ops", "monitoring", "drift"],
    },
    {
        "name": "ModelExplainabilityAgent",
        "module": "ai_data_science_team.agents.model_explainability_agent",
        "class_name": "ModelExplainabilityAgent",
        "description": "Generates explainability artifacts and feature-importance narratives.",
        "capabilities": ["explainability", "feature_importance", "shap"],
        "cost_tier": "medium",
        "category": "ops",
        "tags": ["ops", "explainability", "model"],
    },
    {
        "name": "ResultsSynthesizerAgent",
        "module": "ai_data_science_team.agents.strategic_agents",
        "class_name": "ResultsSynthesizerAgent",
        "description": "Synthesizes analytical outputs into concise result summaries.",
        "capabilities": ["results_synthesis", "summarization", "reporting"],
        "cost_tier": "low",
        "category": "strategy",
        "tags": ["strategy", "synthesis", "reporting"],
    },
    {
        "name": "ContextualKnowledgeAgent",
        "module": "ai_data_science_team.agents.strategic_agents",
        "class_name": "ContextualKnowledgeAgent",
        "description": "Adds business context and supporting knowledge to analytical findings.",
        "capabilities": ["contextual_knowledge", "retrieval", "business_context"],
        "cost_tier": "low",
        "category": "strategy",
        "tags": ["strategy", "context", "knowledge"],
    },
    {
        "name": "NarrativeAgent",
        "module": "ai_data_science_team.agents.strategic_agents",
        "class_name": "NarrativeAgent",
        "description": "Builds user-facing narratives and executive summaries from results.",
        "capabilities": ["narrative_generation", "summarization", "reporting"],
        "cost_tier": "low",
        "category": "strategy",
        "tags": ["strategy", "narrative", "reports"],
    },
    {
        "name": "RecommendationAgent",
        "module": "ai_data_science_team.agents.strategic_agents",
        "class_name": "RecommendationAgent",
        "description": "Turns workflow findings into recommendations and next actions.",
        "capabilities": ["recommendation", "decision_support", "prioritization"],
        "cost_tier": "low",
        "category": "strategy",
        "tags": ["strategy", "recommendation", "decision"],
    },
    {
        "name": "WorkflowPlannerAgent",
        "module": "ai_data_science_team.agents.workflow_planner_agent",
        "class_name": "WorkflowPlannerAgent",
        "description": "Plans candidate workflows before execution and review.",
        "capabilities": ["workflow_planning", "task_breakdown", "routing"],
        "cost_tier": "low",
        "category": "orchestration",
        "tags": ["orchestration", "planning", "workflow"],
    },
    {
        "name": "ApprovalGateAgent",
        "module": "ai_data_science_team.agents.hitl_agent",
        "class_name": "ApprovalGateAgent",
        "description": "Inserts human approval and review checkpoints into workflows.",
        "capabilities": ["approval", "human_in_the_loop", "governance"],
        "cost_tier": "low",
        "category": "human_in_the_loop",
        "tags": ["hitl", "approval", "governance"],
    },
    {
        "name": "OrchestratorAgent",
        "module": "ai_data_science_team.agents.orchestrator_agent",
        "class_name": "OrchestratorAgent",
        "description": "Coordinates dynamic workflow resolution and multi-step execution.",
        "capabilities": ["orchestration", "workflow_resolution", "multi_agent_execution"],
        "cost_tier": "medium",
        "category": "orchestration",
        "tags": ["orchestration", "runtime", "multi-agent"],
    },
)


def _import_agent_class(module_path: str, class_name: str) -> type[Any]:
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def register_production_agent_catalog(*, clear_existing: bool = False) -> dict[str, Any]:
    """Register the production-safe agent catalog used by discovery and M22 rollout."""
    if clear_existing:
        AgentRegistry.clear()

    registered_names: list[str] = []
    skipped: dict[str, str] = {}

    for spec in AGENT_BOOTSTRAP_SPECS:
        name = str(spec["name"])
        try:
            agent_class = _import_agent_class(str(spec["module"]), str(spec["class_name"]))
        except Exception as exc:  # noqa: BLE001
            skipped[name] = str(exc)
            logger.warning("Skipping agent catalog registration for %s: %s", name, exc)
            continue

        AgentRegistry.register(
            name=name,
            agent_class=agent_class,
            capabilities=list(spec.get("capabilities", [])),
            description=str(spec.get("description", "")),
            cost_tier=str(spec.get("cost_tier", "medium")),
            category=str(spec.get("category", "")),
            tags=list(spec.get("tags", [])),
            status=str(spec.get("status", "healthy")),
            overwrite=True,
        )
        registered_names.append(name)

    result = {
        "registered_count": len(registered_names),
        "registered_names": sorted(registered_names),
        "skipped": skipped,
    }
    logger.info(
        "Agent catalog registration complete: %s registered, %s skipped",
        result["registered_count"],
        len(skipped),
    )
    return result
