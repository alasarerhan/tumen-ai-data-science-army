from __future__ import annotations

import sys
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from platform_api.core.config import settings
from platform_api.db.models import Artifact, Tenant, WorkflowRun, Workspace
from platform_api.services import strategy_service


def _make_run(
    *,
    tenant_id: uuid.UUID,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    status: str,
) -> WorkflowRun:
    return WorkflowRun(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        requested_by_user_id=user_id,
        flow_key="hello",
        prefect_flow_run_id=f"run-{uuid.uuid4().hex}",
        status=status,
        parameters_json="{}",
        started_at=None,
        finished_at=None,
    )


def _make_artifact(
    *,
    tenant_id: uuid.UUID,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    kind: str,
) -> Artifact:
    return Artifact(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        workflow_run_id=None,
        kind=kind,
        uri=f"s3://bucket/{uuid.uuid4().hex}.json",
        created_by_user_id=user_id,
    )


def test_gather_workspace_stats_filters_by_tenant_and_workspace(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    user = seeded_db["user_admin"]

    primary_run = _make_run(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user.id,
        status="COMPLETED",
    )
    primary_artifact = _make_artifact(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user.id,
        kind="report",
    )

    other_tenant = Tenant(name="Other Tenant")
    db.add(other_tenant)
    db.flush()
    other_workspace = Workspace(tenant_id=other_tenant.id, name="other-workspace")
    db.add(other_workspace)
    db.flush()
    off_scope_run = _make_run(
        tenant_id=other_tenant.id,
        workspace_id=other_workspace.id,
        user_id=user.id,
        status="FAILED",
    )
    off_scope_artifact = _make_artifact(
        tenant_id=other_tenant.id,
        workspace_id=other_workspace.id,
        user_id=user.id,
        kind="model",
    )
    db.add_all([primary_run, primary_artifact, off_scope_run, off_scope_artifact])
    db.flush()

    # Act
    runs, artifacts = strategy_service._gather_workspace_stats(db, tenant.id, workspace.id)

    # Assert
    assert [run.id for run in runs] == [primary_run.id]
    assert [artifact.id for artifact in artifacts] == [primary_artifact.id]


@pytest.mark.parametrize(
    ("summary", "expected_fragment"),
    [
        (
            {
                "run_count": 10,
                "artifact_count": 10,
                "run_status_distribution": {"FAILED": 6, "COMPLETED": 4},
                "artifact_kind_distribution": {},
            },
            "Failure rate exceeds 50%",
        ),
        (
            {
                "run_count": 10,
                "artifact_count": 10,
                "run_status_distribution": {"FAILED": 2, "COMPLETED": 8},
                "artifact_kind_distribution": {},
            },
            "Some runs are failing",
        ),
        (
            {
                "run_count": 3,
                "artifact_count": 3,
                "run_status_distribution": {"RUNNING": 3},
                "artifact_kind_distribution": {},
            },
            "No run has completed",
        ),
        (
            {
                "run_count": 0,
                "artifact_count": 0,
                "run_status_distribution": {},
                "artifact_kind_distribution": {},
            },
            "No workflows executed yet",
        ),
        (
            {
                "run_count": 10**100,
                "artifact_count": 0,
                "run_status_distribution": {},
                "artifact_kind_distribution": {},
            },
            "Artifact production per run is low",
        ),
        (
            {
                "run_count": 2,
                "artifact_count": 2,
                "run_status_distribution": {"Completed": 2},
                "artifact_kind_distribution": {},
            },
            "Flow appears healthy",
        ),
    ],
)
def test_rule_based_recommendations_covers_core_paths(
    summary: dict[str, object],
    expected_fragment: str,
) -> None:
    # Act
    recommendations = strategy_service._rule_based_recommendations(summary)

    # Assert
    assert any(expected_fragment in recommendation for recommendation in recommendations)


@pytest.mark.asyncio
async def test_openai_recommendations_returns_none_without_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    summary = {
        "run_count": 1,
        "artifact_count": 1,
        "run_status_distribution": {"COMPLETED": 1},
        "artifact_kind_distribution": {"report": 1},
    }
    monkeypatch.setattr(settings, "openai_api_key", "")

    # Act
    recommendations = await strategy_service._openai_recommendations(summary)

    # Assert
    assert recommendations is None


@pytest.mark.asyncio
async def test_openai_recommendations_parses_bullet_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    summary = {
        "run_count": 4,
        "artifact_count": 1,
        "run_status_distribution": {"FAILED": 1, "COMPLETED": 3},
        "artifact_kind_distribution": {"report": 1},
    }
    create_mock = AsyncMock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            "- \u00d6l\u00e7\u00fclebilir hata b\u00fct\u00e7esi tan\u0131mlay\u0131n ve haftal\u0131k trendleri izleyin.\n"
                            "- k\u0131sa\n"
                            "- \u0130\u015f ak\u0131\u015f\u0131nda kritik ad\u0131mlar i\u00e7in otomatik geri deneme uygulay\u0131n."
                        )
                    )
                )
            ]
        )
    )
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create_mock)))
    fake_async_openai = MagicMock(return_value=fake_client)
    fake_openai_module = SimpleNamespace(AsyncOpenAI=fake_async_openai)
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(settings, "openai_model", "gpt-4o-mini")

    # Act
    with patch.dict(sys.modules, {"openai": fake_openai_module}):
        recommendations = await strategy_service._openai_recommendations(summary)

    # Assert
    assert recommendations == [
        "\u00d6l\u00e7\u00fclebilir hata b\u00fct\u00e7esi tan\u0131mlay\u0131n ve haftal\u0131k trendleri izleyin.",
        "\u0130\u015f ak\u0131\u015f\u0131nda kritik ad\u0131mlar i\u00e7in otomatik geri deneme uygulay\u0131n.",
    ]
    fake_async_openai.assert_called_once_with(api_key="test-key")
    create_mock.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "side_effect",
    [
        ImportError("openai package missing"),
        RuntimeError("provider timeout"),
    ],
)
async def test_openai_recommendations_returns_none_and_logs_on_failure(
    monkeypatch: pytest.MonkeyPatch,
    side_effect: Exception,
) -> None:
    # Arrange
    summary = {
        "run_count": 1,
        "artifact_count": 0,
        "run_status_distribution": {"FAILED": 1},
        "artifact_kind_distribution": {},
    }
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    # Act
    if isinstance(side_effect, ImportError):
        with patch.dict(sys.modules, {"openai": None}), patch.object(
            strategy_service.logger,
            "warning",
        ) as warning_mock:
            recommendations = await strategy_service._openai_recommendations(summary)
    else:
        fake_openai_module = SimpleNamespace(AsyncOpenAI=MagicMock(side_effect=side_effect))
        with patch.dict(sys.modules, {"openai": fake_openai_module}), patch.object(
            strategy_service.logger,
            "warning",
        ) as warning_mock:
            recommendations = await strategy_service._openai_recommendations(summary)

    # Assert
    assert recommendations is None
    warning_mock.assert_called_once()


@pytest.mark.asyncio
async def test_generate_workspace_strategy_report_uses_openai_when_available() -> None:
    # Arrange
    runs = [SimpleNamespace(status="COMPLETED"), SimpleNamespace(status="FAILED")]
    artifacts = [SimpleNamespace(kind="report")]
    openai_recommendations = [
        "\u00d6nceliklendirilmi\u015f iyile\u015ftirme plan\u0131 olu\u015fturun."
    ]

    # Act
    with patch(
        "platform_api.services.strategy_service._gather_workspace_stats",
        return_value=(runs, artifacts),
    ), patch(
        "platform_api.services.strategy_service._openai_recommendations",
        new=AsyncMock(return_value=openai_recommendations),
    ):
        report = await strategy_service.generate_workspace_strategy_report(
            db=MagicMock(spec=Session),
            tenant_id=str(uuid.uuid4()),
            workspace_id=str(uuid.uuid4()),
            run_id="run-123",
        )

    # Assert
    assert report["powered_by"] == "openai"
    assert report["recommendations"] == openai_recommendations
    assert report["summary"]["run_count"] == 2
    assert report["summary"]["artifact_count"] == 1
    assert report["summary"]["run_status_distribution"] == {"COMPLETED": 1, "FAILED": 1}
    assert report["run_id"] == "run-123"


@pytest.mark.asyncio
async def test_generate_workspace_strategy_report_falls_back_to_rules() -> None:
    # Arrange
    runs = [SimpleNamespace(status="FAILED")]
    artifacts = []
    fallback_recommendations = [
        "Kural tabanl\u0131 iyile\u015ftirme \u00f6nerisi."
    ]

    # Act
    with patch(
        "platform_api.services.strategy_service._gather_workspace_stats",
        return_value=(runs, artifacts),
    ), patch(
        "platform_api.services.strategy_service._openai_recommendations",
        new=AsyncMock(return_value=None),
    ), patch(
        "platform_api.services.strategy_service._rule_based_recommendations",
        return_value=fallback_recommendations,
    ) as rules_mock:
        report = await strategy_service.generate_workspace_strategy_report(
            db=MagicMock(spec=Session),
            tenant_id=str(uuid.uuid4()),
            workspace_id=str(uuid.uuid4()),
        )

    # Assert
    assert report["powered_by"] == "rules"
    assert report["recommendations"] == fallback_recommendations
    rules_mock.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tenant_id", "workspace_id"),
    [
        ("not-a-uuid", str(uuid.uuid4())),
        (str(uuid.uuid4()), " "),
    ],
)
async def test_generate_workspace_strategy_report_rejects_invalid_uuid_inputs(
    tenant_id: str,
    workspace_id: str,
) -> None:
    # Act / Assert
    with pytest.raises(ValueError):
        await strategy_service.generate_workspace_strategy_report(
            db=MagicMock(spec=Session),
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )


@pytest.mark.parametrize(
    ("status_name", "kind_name"),
    [
        ("COMPLETED", "report"),
        ("FAILED", "model"),
        ("T\u00fcrk\u00e7e-\u0130sim", "\u00f6zet-\u00e7\u0131kt\u0131"),
        (" " * 3, "\U0001F4CA"),
    ],
)
def test_summary_counters_handle_unicode_and_whitespace_values(
    status_name: str,
    kind_name: str,
) -> None:
    # Arrange
    runs = [SimpleNamespace(status=status_name)]
    artifacts = [SimpleNamespace(kind=kind_name)]

    # Act
    run_counter = strategy_service.Counter(run.status for run in runs)
    artifact_counter = strategy_service.Counter(artifact.kind for artifact in artifacts)

    # Assert
    assert dict(run_counter) == {status_name: 1}
    assert dict(artifact_counter) == {kind_name: 1}
