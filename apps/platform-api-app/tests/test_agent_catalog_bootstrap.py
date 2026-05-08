from __future__ import annotations

from ai_data_science_team.agent_registry import AgentRegistry
from fastapi.testclient import TestClient

from platform_api.main import create_app
from platform_api.orchestration.agent_catalog import register_production_agent_catalog


def test_register_production_agent_catalog_registers_expected_core_agents() -> None:
    AgentRegistry.clear()
    try:
        result = register_production_agent_catalog(clear_existing=True)
        names = set(result["registered_names"])
        assert result["registered_count"] >= 5
        assert {"DataCleaningAgent", "EDAToolsAgent", "WorkflowPlannerAgent"} <= names
        catalog = AgentRegistry.to_catalog()
        entry = next(agent for agent in catalog if agent["name"] == "DataCleaningAgent")
        assert entry["category"] == "data"
        assert entry["status"] == "healthy"
    finally:
        AgentRegistry.clear()


def test_app_startup_populates_agent_catalog_registration_state() -> None:
    AgentRegistry.clear()
    app = create_app()
    try:
        with TestClient(app):
            state = app.state.agent_catalog_registration
            assert state["registered_count"] >= 5
            assert "DataCleaningAgent" in state["registered_names"]
    finally:
        AgentRegistry.clear()
