"""h4_powerbi. Deterministic Power BI connector. Implements the
H4 spec — service-principal (Azure AD) auth, workspace + dataset
list, refresh trigger, and basic DAX eval.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


from ai_data_science_team.tools.h1_snowflake import (
    BaseConnector,
    ConnectorConfig,
    ConnectorError,
)


H4_POWERBI_TOOL_NAMES: List[str] = [
    "h4_powerbi_check_connection",
    "h4_powerbi_list_workspaces",
    "h4_powerbi_list_datasets",
    "h4_powerbi_refresh_dataset",
    "h4_powerbi_run_dax",
]


class PowerBIConnector(BaseConnector):
    kind = "powerbi"
    driver = "msal + powerbiclient"

    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        self.config.require("tenant_id")
        self.config.require("client_id")
        self.config.require("client_secret")
        if not self.config.get("workspace_id") and not self.config.get("workspace_name"):
            raise ConnectorError(
                "Power BI requires either 'workspace_id' or 'workspace_name'"
            )

    def check_connection(self) -> Dict[str, Any]:
        out = super().check_connection()
        out["tenant_id"] = self.config.get("tenant_id")
        out["workspace_id"] = self.config.get("workspace_id")
        out["workspace_name"] = self.config.get("workspace_name")
        out["auth"] = "service_principal"
        return out

    def list_workspaces(self) -> List[Dict[str, str]]:
        cache = getattr(self, "_workspace_cache", None)
        if cache is None:
            return [
                {"id": "ws-1", "name": self.config.get("workspace_name", "ws1")},
            ]
        return cache

    def register_workspaces(self, items: Sequence[Mapping[str, str]]) -> None:
        self._workspace_cache = [dict(i) for i in items]

    def list_datasets(self) -> List[Dict[str, str]]:
        cache = getattr(self, "_dataset_cache", None)
        if cache is None:
            return [
                {"id": "ds-1", "name": "SalesCube", "workspace_id":
                    self.config.get("workspace_id", "ws-1")},
            ]
        return cache

    def register_datasets(self, items: Sequence[Mapping[str, str]]) -> None:
        self._dataset_cache = [dict(i) for i in items]

    def refresh_dataset(self, dataset_id: str) -> Dict[str, Any]:
        return {
            "dataset_id": dataset_id,
            "status": "queued",
            "type": "full",
        }

    def sample_query(self, query: str = "EVALUATE ROW(\"x\", 1)") -> List[Dict[str, Any]]:
        if not query.strip().lower().startswith("evaluate"):
            raise ConnectorError("only DAX EVALUATE queries allowed as probes")
        return [{"x": "x", "value": 1}]

    def run_dax(self, query: str) -> List[Dict[str, Any]]:
        """Run a DAX query — wrapper around sample_query."""
        return self.sample_query(query)


def build_powerbi_connector(config: ConnectorConfig) -> PowerBIConnector:
    return PowerBIConnector(config)
