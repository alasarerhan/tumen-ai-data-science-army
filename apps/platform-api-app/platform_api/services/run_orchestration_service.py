from __future__ import annotations

from dataclasses import dataclass
import logging
import uuid
from typing import Any, Protocol

from platform_api.core.config import settings
from platform_api.core.service_errors import UpstreamUnavailableError, ValidationError
from platform_api.orchestration.prefect_gateway import PrefectGateway, PrefectGatewayConfig
from platform_api.orchestration.runtime_state import (
    get_orchestration_context_store,
    validate_runtime_state_settings,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OrchestrationRunRequest:
    flow_key: str
    parameters: dict[str, Any]
    workspace_id: str | None = None
    user_id: str | None = None
    tenant_id: str | None = None


class OrchestrationExecutionAdapter(Protocol):
    async def create_run(self, request: OrchestrationRunRequest) -> str: ...

    async def read_run(self, flow_run_id: str) -> dict[str, Any]: ...


def _gateway() -> PrefectGateway:
    return PrefectGateway(
        PrefectGatewayConfig(
            hello_deployment_id=settings.prefect_hello_deployment_id,
            default_deployment_id=settings.prefect_default_deployment_id,
        )
    )


def validate_orchestration_runtime_settings(*, raise_runtime: bool = False) -> None:
    mode = settings.orchestration_execution_mode.strip().lower()
    allowed_modes = {"prefect", "staged_m22"}
    if mode not in allowed_modes:
        message = (
            "Invalid orchestration execution mode. "
            "Expected one of: prefect, staged_m22."
        )
        if raise_runtime:
            raise RuntimeError(message)
        raise ValidationError(message)

    if mode == "staged_m22" and not settings.is_local_or_staging_profile():
        message = (
            "staged_m22 orchestration mode is only allowed in local or staging profiles "
            "until lifecycle parity is proven."
        )
        if raise_runtime:
            raise RuntimeError(message)
        raise ValidationError(message)

    validate_runtime_state_settings(raise_runtime=raise_runtime)


class PrefectExecutionAdapter:
    async def create_run(self, request: OrchestrationRunRequest) -> str:
        gateway = _gateway()
        try:
            return await gateway.create_flow_run(flow_key=request.flow_key, parameters=request.parameters or {})
        except ValueError as exc:
            if settings.is_local_profile() and settings.allow_local_run_fallback:
                logger.warning(
                    "LOCAL FALLBACK: Creating local run ID due to ValueError. "
                    "This should only happen in development."
                )
                return f"local-{uuid.uuid4().hex[:12]}"
            logger.error("Orchestration run creation failed (ValueError): %s", exc)
            raise ValidationError(str(exc)) from exc
        except Exception as exc:
            if settings.is_local_profile() and settings.allow_local_run_fallback:
                logger.warning(
                    "LOCAL FALLBACK: Creating local run ID due to orchestration failure. "
                    "This should only happen in development."
                )
                return f"local-{uuid.uuid4().hex[:12]}"
            logger.error("Orchestration run creation failed: %s", exc)
            raise UpstreamUnavailableError(
                f"Failed to create orchestration run: {exc}"
            ) from exc

    async def read_run(self, flow_run_id: str) -> dict[str, Any]:
        gateway = _gateway()
        return await gateway.read_flow_run(flow_run_id)


class StagedM22ExecutionAdapter:
    def __init__(self, delegate: PrefectExecutionAdapter | None = None) -> None:
        self._delegate = delegate or PrefectExecutionAdapter()

    async def create_run(self, request: OrchestrationRunRequest) -> str:
        flow_run_id = await self._delegate.create_run(request)
        store = get_orchestration_context_store()
        if not store.session_exists(flow_run_id):
            store.create_session(
                session_id=flow_run_id,
                user_id=request.user_id,
                workspace_id=request.workspace_id,
                scenario="platform_api_run",
                metadata={
                    "tenant_id": request.tenant_id,
                    "flow_key": request.flow_key,
                    "execution_mode": "staged_m22",
                    "parameter_keys": sorted(request.parameters.keys()),
                },
            )
        store.set(flow_run_id, "run_parameters", request.parameters)
        return flow_run_id

    async def read_run(self, flow_run_id: str) -> dict[str, Any]:
        return await self._delegate.read_run(flow_run_id)


def _select_adapter() -> OrchestrationExecutionAdapter:
    validate_orchestration_runtime_settings()
    mode = settings.orchestration_execution_mode.strip().lower()
    if mode == "staged_m22":
        return StagedM22ExecutionAdapter()
    return PrefectExecutionAdapter()


async def create_orchestration_run_id(
    *,
    flow_key: str,
    parameters: dict | None = None,
    workspace_id: str | None = None,
    user_id: str | None = None,
    tenant_id: str | None = None,
) -> str:
    request = OrchestrationRunRequest(
        flow_key=flow_key,
        parameters=parameters or {},
        workspace_id=workspace_id,
        user_id=user_id,
        tenant_id=tenant_id,
    )
    return await _select_adapter().create_run(request)


async def read_orchestration_run(flow_run_id: str) -> dict:
    return await _select_adapter().read_run(flow_run_id)
