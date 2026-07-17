"""Unit tests for the agent discovery service."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from platform_api.discovery.agent_discovery import AgentDiscoveryService


class TestAgentDiscoveryService:
    """Tests for AgentDiscoveryService class."""

    @pytest.fixture
    def service(self) -> AgentDiscoveryService:
        return AgentDiscoveryService(pinecone_api_key=None, index_name=None)

    @pytest.mark.asyncio
    async def test_fallback_search_finds_matching_agents(
        self,
        service: AgentDiscoveryService,
    ) -> None:
        with patch.object(service, "_fallback_search", new_callable=AsyncMock) as mock_fallback:
            mock_fallback.return_value = [
                {"name": "DataLoaderAgent", "score": 3},
                {"name": "DataCleanerAgent", "score": 2},
            ]

            results = await service.search("load data")

            assert len(results) == 2
            assert results[0]["name"] == "DataLoaderAgent"

    @pytest.mark.asyncio
    async def test_search_with_filters(
        self,
        service: AgentDiscoveryService,
    ) -> None:
        with patch.object(service, "_fallback_search", new_callable=AsyncMock) as mock_fallback:
            mock_fallback.return_value = [
                {"name": "ModelTrainingAgent", "category": "machine_learning"},
            ]

            await service.search(
                "train model",
                filters={"category": "machine_learning"},
            )

            mock_fallback.assert_called_once_with(
                "train model",
                {"category": "machine_learning"},
                20,
            )

    @pytest.mark.asyncio
    async def test_browse_by_category(
        self,
        service: AgentDiscoveryService,
    ) -> None:
        with patch("platform_api.discovery.agent_discovery.AgentRegistry") as mock_registry:
            mock_registry.to_catalog.return_value = [
                {"name": "DataLoaderAgent", "category": "eda"},
                {"name": "ModelTrainingAgent", "category": "machine_learning"},
            ]

            results = await service.browse(category="eda")

            assert len(results) == 1
            assert results[0]["name"] == "DataLoaderAgent"

    @pytest.mark.asyncio
    async def test_browse_by_capabilities(
        self,
        service: AgentDiscoveryService,
    ) -> None:
        with patch("platform_api.discovery.agent_discovery.AgentRegistry") as mock_registry:
            mock_registry.to_catalog.return_value = [
                {"name": "DataLoaderAgent", "capabilities": ["load_csv", "load_excel"]},
                {"name": "ModelTrainingAgent", "capabilities": ["train_model", "evaluate"]},
            ]

            results = await service.browse(capabilities=["load_csv"])

            assert len(results) == 1
            assert results[0]["name"] == "DataLoaderAgent"

    @pytest.mark.asyncio
    async def test_browse_by_tags(
        self,
        service: AgentDiscoveryService,
    ) -> None:
        with patch("platform_api.discovery.agent_discovery.AgentRegistry") as mock_registry:
            mock_registry.to_catalog.return_value = [
                {"name": "DataLoaderAgent", "tags": ["data", "ingestion"]},
                {"name": "ModelTrainingAgent", "tags": ["ml", "training"]},
            ]

            results = await service.browse(tags=["data"])

            assert len(results) == 1
            assert results[0]["name"] == "DataLoaderAgent"

    @pytest.mark.asyncio
    async def test_browse_by_cost_tier(
        self,
        service: AgentDiscoveryService,
    ) -> None:
        with patch("platform_api.discovery.agent_discovery.AgentRegistry") as mock_registry:
            mock_registry.to_catalog.return_value = [
                {"name": "DataLoaderAgent", "cost_tier": "low"},
                {"name": "ModelTrainingAgent", "cost_tier": "high"},
            ]

            results = await service.browse(cost_tier="low")

            assert len(results) == 1
            assert results[0]["name"] == "DataLoaderAgent"

    @pytest.mark.asyncio
    async def test_recommend_extracts_capabilities(
        self,
        service: AgentDiscoveryService,
    ) -> None:
        workflow_spec = {
            "steps": [
                {"agent": "DataLoaderAgent"},
            ],
            "description": "analyze data and detect anomalies",
        }

        with patch.object(service, "_find_by_capabilities", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = [
                {"name": "AnomalyDetectionAgent", "capability_overlap": 2},
            ]

            results = await service.recommend(workflow_spec)

            assert len(results) == 1
            assert results[0]["name"] == "AnomalyDetectionAgent"

    @pytest.mark.asyncio
    async def test_recommend_excludes_existing_agents(
        self,
        service: AgentDiscoveryService,
    ) -> None:
        workflow_spec = {
            "steps": [
                {"agent": "DataLoaderAgent"},
            ],
        }

        with patch.object(service, "_find_by_capabilities", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = [
                {"name": "DataLoaderAgent", "capability_overlap": 5},
                {"name": "DataCleanerAgent", "capability_overlap": 3},
            ]

            results = await service.recommend(workflow_spec)

            assert len(results) == 1
            assert results[0]["name"] == "DataCleanerAgent"

    @pytest.mark.asyncio
    async def test_get_categories(
        self,
        service: AgentDiscoveryService,
    ) -> None:
        with patch("platform_api.discovery.agent_discovery.AGENT_CATEGORIES", {"eda": {"name": "EDA"}}):
            results = await service.get_categories()

            assert len(results) == 1
            assert results[0]["key"] == "eda"

    @pytest.mark.asyncio
    async def test_index_agents_without_pinecone(
        self,
        service: AgentDiscoveryService,
    ) -> None:
        service._index = None

        count = await service.index_agents()

        assert count == 0

    @pytest.mark.asyncio
    async def test_browse_uses_default_catalog_when_registry_empty(
        self,
        service: AgentDiscoveryService,
    ) -> None:
        with patch("platform_api.discovery.agent_discovery.AgentRegistry") as mock_registry:
            mock_registry.to_catalog.return_value = []

            results = await service.browse()

            assert len(results) >= 1
            assert any(agent["name"] == "EDA Analyst" for agent in results)

    def test_extract_capabilities_from_workflow(
        self,
        service: AgentDiscoveryService,
    ) -> None:
        workflow_spec = {
            "steps": [
                {"agent": "DataLoaderAgent"},
            ],
            "description": "analyze data and detect anomalies",
        }

        with patch("platform_api.discovery.agent_discovery.AgentRegistry") as mock_registry:
            mock_agent = MagicMock()
            mock_agent.capabilities = ["load_csv", "load_excel"]
            mock_registry.get_or_none.return_value = mock_agent

            capabilities = service._extract_capabilities(workflow_spec)

            assert "load_csv" in capabilities
            assert "load_excel" in capabilities

    def test_check_threshold_x_baseline(
        self,
        service: AgentDiscoveryService,
    ) -> None:
        metrics = {"baseline": {"error_rate": 0.02}}

        assert service._check_threshold(0.05, "2x_baseline", metrics) is True
        assert service._check_threshold(0.03, "2x_baseline", metrics) is False

    def test_check_threshold_milliseconds(
        self,
        service: AgentDiscoveryService,
    ) -> None:
        assert service._check_threshold(6000, "5000ms", {}) is True
        assert service._check_threshold(4000, "5000ms", {}) is False

    def test_check_threshold_percentage(
        self,
        service: AgentDiscoveryService,
    ) -> None:
        assert service._check_threshold(85, "90%", {}) is True
        assert service._check_threshold(95, "90%", {}) is False
