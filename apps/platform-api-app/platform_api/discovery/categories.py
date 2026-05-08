"""Agent categories for discovery and browsing.

This module defines the category structure for organizing agents
in the visual workflow builder and discovery interface.
"""

from __future__ import annotations

from typing import Any, Dict, List


AGENT_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "data_processing": {
        "name": "Data Processing",
        "icon": "📊",
        "description": "Load, clean, transform, and prepare data for analysis",
        "agents": [
            "DataLoaderAgent",
            "DataCleaningAgent",
            "DataWranglingAgent",
        ],
        "capabilities": [
            "data_loading",
            "data_cleaning",
            "data_transformation",
            "preprocessing",
        ],
    },
    "analysis": {
        "name": "Analysis & EDA",
        "icon": "🔬",
        "description": "Explore data, detect anomalies, and generate insights",
        "agents": [
            "EDAAgent",
            "AnomalyDetectionAgent",
            "SQLDatabaseAgent",
        ],
        "capabilities": [
            "exploratory_analysis",
            "anomaly_detection",
            "sql_querying",
            "profiling",
        ],
    },
    "machine_learning": {
        "name": "Machine Learning",
        "icon": "🤖",
        "description": "Feature engineering, model training, and serving",
        "agents": [
            "FeatureEngineeringAgent",
            "ModelTrainingAgent",
            "ModelServingAgent",
        ],
        "capabilities": [
            "feature_engineering",
            "model_training",
            "model_serving",
            "ml_preprocessing",
        ],
    },
    "visualization": {
        "name": "Visualization",
        "icon": "📈",
        "description": "Create charts, dashboards, and reports",
        "agents": [
            "DataVisualizationAgent",
        ],
        "capabilities": [
            "visualization",
            "plotting",
            "dashboard_creation",
            "reporting",
        ],
    },
    "orchestration": {
        "name": "Orchestration",
        "icon": "🎯",
        "description": "Coordinate workflows and manage agent execution",
        "agents": [
            "OrchestratorAgent",
            "HITLAgent",
        ],
        "capabilities": [
            "orchestration",
            "coordination",
            "human_in_the_loop",
            "workflow_management",
        ],
    },
}


def get_category_for_agent(agent_name: str) -> str:
    """Get the category for an agent.
    
    Parameters
    ----------
    agent_name : str
        The name of the agent.
    
    Returns
    -------
    str
        The category key, or "general" if not found.
    """
    for category_key, category_data in AGENT_CATEGORIES.items():
        if agent_name in category_data.get("agents", []):
            return category_key
    return "general"


def get_agents_in_category(category: str) -> List[str]:
    """Get all agents in a category.
    
    Parameters
    ----------
    category : str
        The category key.
    
    Returns
    -------
    List[str]
        List of agent names in the category.
    """
    category_data = AGENT_CATEGORIES.get(category, {})
    return category_data.get("agents", [])


def get_capabilities_for_category(category: str) -> List[str]:
    """Get all capabilities for a category.
    
    Parameters
    ----------
    category : str
        The category key.
    
    Returns
    -------
    List[str]
        List of capabilities.
    """
    category_data = AGENT_CATEGORIES.get(category, {})
    return category_data.get("capabilities", [])


def get_all_capabilities() -> List[str]:
    """Get all unique capabilities across all categories.
    
    Returns
    -------
    List[str]
        List of all capabilities.
    """
    capabilities = set()
    for category_data in AGENT_CATEGORIES.values():
        capabilities.update(category_data.get("capabilities", []))
    return sorted(list(capabilities))


def get_category_metadata(category: str) -> Dict[str, Any]:
    """Get full metadata for a category.
    
    Parameters
    ----------
    category : str
        The category key.
    
    Returns
    -------
    Dict[str, Any]
        Category metadata.
    """
    return AGENT_CATEGORIES.get(category, {
        "name": category.title(),
        "icon": "📦",
        "description": "",
        "agents": [],
        "capabilities": [],
    })
