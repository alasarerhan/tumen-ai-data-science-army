from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PrefectGatewayConfig:
    hello_deployment_id: str
    default_deployment_id: str = ""


class PrefectGateway:
    def __init__(self, config: PrefectGatewayConfig) -> None:
        self._config = config

    def _deployment_id_for_flow_key(self, flow_key: str) -> str:
        if flow_key == "hello":
            return self._config.hello_deployment_id
        return self._config.default_deployment_id

    async def create_flow_run(self, *, flow_key: str, parameters: dict | None = None) -> str:
        deployment_id = self._deployment_id_for_flow_key(flow_key)
        if not deployment_id:
            raise ValueError(f"Missing Prefect deployment id for flow_key='{flow_key}'")

        from prefect.client.orchestration import get_client

        async with get_client() as client:
            flow_run = await client.create_flow_run_from_deployment(
                deployment_id=deployment_id,
                parameters=parameters or {},
            )
            return str(flow_run.id)

    async def create_hello_flow_run(self, parameters: dict | None = None) -> str:
        return await self.create_flow_run(flow_key="hello", parameters=parameters)

    async def read_flow_run(self, flow_run_id: str) -> dict:
        from prefect.client.orchestration import get_client

        async with get_client() as client:
            flow_run = await client.read_flow_run(flow_run_id)

        state_name = getattr(flow_run.state, "name", None) if flow_run.state else None
        state_type = getattr(flow_run.state, "type", None) if flow_run.state else None

        return {
            "id": str(flow_run.id),
            "name": flow_run.name,
            "state": {
                "name": str(state_name) if state_name else None,
                "type": str(state_type) if state_type else None,
            },
            "start_time": flow_run.start_time.isoformat() if flow_run.start_time else None,
            "end_time": flow_run.end_time.isoformat() if flow_run.end_time else None,
        }
