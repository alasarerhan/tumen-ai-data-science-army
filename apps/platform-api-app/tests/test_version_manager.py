"""Unit tests for the workflow version manager."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from platform_api.versioning.version_manager import WorkflowVersionManager


class TestWorkflowVersionManager:
    """Tests for WorkflowVersionManager class."""

    @pytest.fixture
    def mock_db(self) -> MagicMock:
        db = MagicMock()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.query = MagicMock()
        return db

    @pytest.fixture
    def manager(self, mock_db: MagicMock) -> WorkflowVersionManager:
        return WorkflowVersionManager(mock_db, redis=None)

    @pytest.mark.asyncio
    async def test_create_version_first_version(
        self,
        manager: WorkflowVersionManager,
        mock_db: MagicMock,
    ) -> None:
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            None
        )

        version_id = await manager.create_version(
            workflow_id="wf-123",
            workflow_spec={"name": "Test Workflow", "steps": []},
            changelog="Initial version",
            created_by="user-1",
        )

        assert version_id is not None
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_version_increments_version(
        self,
        manager: WorkflowVersionManager,
        mock_db: MagicMock,
    ) -> None:
        existing_version = MagicMock()
        existing_version.version = 2
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            existing_version
        )

        version_id = await manager.create_version(
            workflow_id="wf-123",
            workflow_spec={"name": "Test Workflow", "steps": []},
            changelog="Updated version",
            created_by="user-1",
        )

        assert version_id is not None
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_deploy_version_canary_strategy(
        self,
        manager: WorkflowVersionManager,
        mock_db: MagicMock,
    ) -> None:
        version = MagicMock()
        version.id = "v-123"
        version.workflow_id = "wf-123"
        version.status = "draft"

        manager._get_version = AsyncMock(return_value=version)

        result = await manager.deploy_version("v-123", strategy="canary")

        assert result["status"] == "canary_5%"
        assert result["traffic"] == 0.05
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_deploy_version_full_strategy(
        self,
        manager: WorkflowVersionManager,
        mock_db: MagicMock,
    ) -> None:
        version = MagicMock()
        version.id = "v-123"
        version.status = "draft"

        manager._get_version = AsyncMock(return_value=version)

        result = await manager.deploy_version("v-123", strategy="full")

        assert result["status"] == "published"
        assert result["strategy"] == "full"

    @pytest.mark.asyncio
    async def test_deploy_version_raises_for_non_draft(
        self,
        manager: WorkflowVersionManager,
    ) -> None:
        version = MagicMock()
        version.status = "published"

        manager._get_version = AsyncMock(return_value=version)

        with pytest.raises(ValueError, match="not in draft status"):
            await manager.deploy_version("v-123", strategy="canary")

    @pytest.mark.asyncio
    async def test_deploy_version_raises_for_not_found(
        self,
        manager: WorkflowVersionManager,
    ) -> None:
        manager._get_version = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await manager.deploy_version("v-123", strategy="canary")

    @pytest.mark.asyncio
    async def test_advance_canary(
        self,
        manager: WorkflowVersionManager,
        mock_db: MagicMock,
    ) -> None:
        deployment = MagicMock()
        deployment.id = "d-123"
        deployment.current_stage = 0
        deployment.stages = [
            {"stage": 0, "traffic": 0.05},
            {"stage": 1, "traffic": 0.25},
            {"stage": 2, "traffic": 1.0},
        ]

        mock_db.get.return_value = deployment

        result = await manager.advance_canary("d-123")

        assert result["status"] == "canary_25%"
        assert result["traffic"] == 0.25
        assert result["stage"] == 1

    @pytest.mark.asyncio
    async def test_advance_canary_completes_at_final_stage(
        self,
        manager: WorkflowVersionManager,
        mock_db: MagicMock,
    ) -> None:
        deployment = MagicMock()
        deployment.id = "d-123"
        deployment.current_stage = 2
        deployment.stages = [
            {"stage": 0, "traffic": 0.05},
            {"stage": 1, "traffic": 0.25},
            {"stage": 2, "traffic": 1.0},
        ]

        mock_db.get.return_value = deployment

        result = await manager.advance_canary("d-123")

        assert result["status"] == "completed"
        assert result["traffic"] == 1.0

    @pytest.mark.asyncio
    async def test_advance_canary_raises_for_not_found(
        self,
        manager: WorkflowVersionManager,
        mock_db: MagicMock,
    ) -> None:
        mock_db.get.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await manager.advance_canary("d-123")

    @pytest.mark.asyncio
    async def test_check_rollback_triggers_no_triggers(
        self,
        manager: WorkflowVersionManager,
        mock_db: MagicMock,
    ) -> None:
        deployment = MagicMock()
        deployment.id = "d-123"
        deployment.workflow_id = "wf-123"
        deployment.rollback_triggers = [
            {"metric": "error_rate", "threshold": "2x_baseline"},
        ]

        mock_db.get.return_value = deployment

        metrics = {
            "error_rate": 0.01,
            "baseline": {"error_rate": 0.02},
        }

        result = await manager.check_rollback_triggers("d-123", metrics)

        assert result["rollback_triggered"] is False
        assert result["triggers_hit"] == []

    @pytest.mark.asyncio
    async def test_get_version_history(
        self,
        manager: WorkflowVersionManager,
        mock_db: MagicMock,
    ) -> None:
        versions = [
            MagicMock(to_dict=MagicMock(return_value={"version": 2})),
            MagicMock(to_dict=MagicMock(return_value={"version": 1})),
        ]
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = versions

        result = await manager.get_version_history("wf-123", limit=10)

        assert len(result) == 2
        assert result[0]["version"] == 2
        assert result[1]["version"] == 1
