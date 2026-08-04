from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from platform_api.services import run_orchestration_service


def test_gateway_uses_settings_for_prefect_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setattr(
        run_orchestration_service.settings, "prefect_hello_deployment_id", "hello-deploy"
    )
    monkeypatch.setattr(
        run_orchestration_service.settings, "prefect_default_deployment_id", "default-deploy"
    )

    # Act
    gateway = run_orchestration_service._gateway()

    # Assert
    assert gateway._config.hello_deployment_id == "hello-deploy"
    assert gateway._config.default_deployment_id == "default-deploy"


@pytest.mark.asyncio
async def test_create_orchestration_run_id_returns_gateway_run_id() -> None:
    # Arrange
    gateway = MagicMock()
    gateway.create_flow_run = AsyncMock(return_value="prefect-run-123")

    # Act
    with patch("platform_api.services.run_orchestration_service._gateway", return_value=gateway):
        run_id = await run_orchestration_service.create_orchestration_run_id(
            flow_key="hello",
            parameters=None,
        )

    # Assert
    assert run_id == "prefect-run-123"
    gateway.create_flow_run.assert_awaited_once_with(flow_key="hello", parameters={})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("side_effect", "expected_status", "expected_detail"),
    [
        (ValueError("Missing deployment id"), 400, "Missing deployment id"),
        (
            RuntimeError("Prefect unavailable"),
            502,
            "Failed to create orchestration run: Prefect unavailable",
        ),
    ],
)
async def test_create_orchestration_run_id_raises_http_exception_when_fallback_disabled(
    monkeypatch: pytest.MonkeyPatch,
    side_effect: Exception,
    expected_status: int,
    expected_detail: str,
) -> None:
    # Arrange
    gateway = MagicMock()
    gateway.create_flow_run = AsyncMock(side_effect=side_effect)
    monkeypatch.setattr(run_orchestration_service.settings, "allow_local_run_fallback", False)

    # Act
    with (
        patch("platform_api.services.run_orchestration_service._gateway", return_value=gateway),
        patch.object(
            type(run_orchestration_service.settings),
            "is_local_profile",
            return_value=False,
        ),
        pytest.raises(HTTPException, match=expected_detail) as exc_info,
    ):
        await run_orchestration_service.create_orchestration_run_id(
            flow_key="unknown-flow",
            parameters={"k": "v"},
        )

    # Assert
    assert exc_info.value.status_code == expected_status
    assert isinstance(exc_info.value.__cause__, type(side_effect))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "side_effect",
    [
        ValueError("no deployment"),
        RuntimeError("network timeout"),
    ],
)
async def test_create_orchestration_run_id_returns_local_fallback_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
    side_effect: Exception,
) -> None:
    # Arrange
    gateway = MagicMock()
    gateway.create_flow_run = AsyncMock(side_effect=side_effect)
    monkeypatch.setattr(run_orchestration_service.settings, "allow_local_run_fallback", True)
    fixed_uuid = uuid.UUID("12345678-1234-5678-9abc-def012345678")

    # Act
    with (
        patch("platform_api.services.run_orchestration_service._gateway", return_value=gateway),
        patch.object(
            type(run_orchestration_service.settings),
            "is_local_profile",
            return_value=True,
        ),
        patch(
            "platform_api.services.run_orchestration_service.uuid.uuid4", return_value=fixed_uuid
        ),
    ):
        run_id = await run_orchestration_service.create_orchestration_run_id(
            flow_key="any",
            parameters={"x": 1},
        )

    # Assert
    assert run_id == "local-123456781234"
    gateway.create_flow_run.assert_awaited_once_with(flow_key="any", parameters={"x": 1})


@pytest.mark.asyncio
async def test_read_orchestration_run_returns_gateway_payload() -> None:
    # Arrange
    expected_payload = {"id": "run-xyz", "state": {"name": "Running"}}
    gateway = MagicMock()
    gateway.read_flow_run = AsyncMock(return_value=expected_payload)

    # Act
    with patch("platform_api.services.run_orchestration_service._gateway", return_value=gateway):
        payload = await run_orchestration_service.read_orchestration_run("run-xyz")

    # Assert
    assert payload == expected_payload
    gateway.read_flow_run.assert_awaited_once_with("run-xyz")


def test_validate_orchestration_runtime_settings_rejects_staged_mode_in_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        run_orchestration_service.settings, "orchestration_execution_mode", "staged_m22"
    )
    with (
        patch.object(
            type(run_orchestration_service.settings),
            "is_local_or_staging_profile",
            return_value=False,
        ),
        pytest.raises(RuntimeError, match="only allowed in local or staging profiles"),
    ):
        run_orchestration_service.validate_orchestration_runtime_settings(raise_runtime=True)


@pytest.mark.asyncio
async def test_staged_m22_mode_bootstraps_context_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = MagicMock()
    gateway.create_flow_run = AsyncMock(return_value="prefect-run-123")
    store = SimpleNamespace(
        session_exists=MagicMock(return_value=False),
        create_session=MagicMock(),
        set=MagicMock(),
    )
    monkeypatch.setattr(
        run_orchestration_service.settings, "orchestration_execution_mode", "staged_m22"
    )
    monkeypatch.setattr(
        run_orchestration_service.settings, "orchestration_state_redis_url", "redis://runtime-state"
    )
    with (
        patch.object(
            type(run_orchestration_service.settings),
            "is_local_or_staging_profile",
            return_value=True,
        ),
        patch("platform_api.services.run_orchestration_service._gateway", return_value=gateway),
        patch(
            "platform_api.services.run_orchestration_service.get_orchestration_context_store",
            return_value=store,
        ),
    ):
        run_id = await run_orchestration_service.create_orchestration_run_id(
            flow_key="hello",
            parameters={"requested_by": "user-1", "x": 1},
            workspace_id="ws-1",
            user_id="user-id-1",
            tenant_id="tenant-1",
        )

    assert run_id == "prefect-run-123"
    store.create_session.assert_called_once()
    _, kwargs = store.create_session.call_args
    assert kwargs["session_id"] == "prefect-run-123"
    assert kwargs["workspace_id"] == "ws-1"
    assert kwargs["metadata"]["execution_mode"] == "staged_m22"
    store.set.assert_called_once_with(
        "prefect-run-123", "run_parameters", {"requested_by": "user-1", "x": 1}
    )


def test_validate_orchestration_runtime_settings_requires_redis_url_for_staged_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        run_orchestration_service.settings, "orchestration_execution_mode", "staged_m22"
    )
    monkeypatch.setattr(run_orchestration_service.settings, "orchestration_state_redis_url", "")
    with (
        patch.object(
            type(run_orchestration_service.settings),
            "is_local_or_staging_profile",
            return_value=True,
        ),
        pytest.raises(HTTPException, match="orchestration_state_redis_url must be set"),
    ):
        run_orchestration_service.validate_orchestration_runtime_settings()
