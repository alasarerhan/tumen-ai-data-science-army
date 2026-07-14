"""h2_bigquery. Deterministic BigQuery connector. Implements the
H2 spec — service-account / OAuth auth, project + dataset, query
probe, schema introspection.  ``google-cloud-bigquery`` is referenced
but not bundled; the deterministic core handles auth validation
and exposes the same check/sample/schema contract as the rest
of the connector family.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


from ai_data_science_team.tools.h1_snowflake import (
    BaseConnector,
    ConnectorConfig,
    ConnectorError,
)


H2_BIGQUERY_TOOL_NAMES: List[str] = [
    "h2_bigquery_check_connection",
    "h2_bigquery_sample_query",
    "h2_bigquery_schema_introspect",
    "h2_bigquery_query_cost_estimate",
]


class BigQueryConnector(BaseConnector):
    kind = "bigquery"
    driver = "google-cloud-bigquery"

    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        self.config.require("project")
        self.config.require("dataset")
        auth = self.config.get("auth", "service_account")
        if auth == "service_account":
            self.config.require("credentials_path")
        elif auth == "oauth":
            if not self.config.get("oauth_token"):
                raise ConnectorError("auth='oauth' requires 'oauth_token'")
        else:
            raise ConnectorError(f"unknown BigQuery auth method {auth!r}")
        self._auth = auth

    def check_connection(self) -> Dict[str, Any]:
        out = super().check_connection()
        out["project"] = self.config.get("project")
        out["dataset"] = self.config.get("dataset")
        out["auth"] = self._auth
        out["location"] = self.config.get("location", "US")
        return out

    def sample_query(self, query: str = "SELECT 1") -> List[Dict[str, Any]]:
        if not query.strip().lower().startswith("select"):
            raise ConnectorError("only SELECT queries allowed")
        # BigQuery deterministic probe: project + current timestamp.
        return [
            {
                "select_1": 1,
                "project": self.config.get("project"),
                "dataset": self.config.get("dataset"),
            }
        ]

    def schema_introspect(self, table: str) -> List[Dict[str, str]]:
        try:
            return super().schema_introspect(table)
        except ConnectorError:
            pass
        cache = getattr(self, "_schema_cache", {})
        if table not in cache:
            raise ConnectorError(
                f"unknown BigQuery table {table!r}; seed _schema_cache "
                "or use a real driver"
            )
        return cache[table]

    def query_cost_estimate(
        self, query: str, bytes_processed: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Crude cost estimate: 5 $/TB processed."""
        if bytes_processed is None:
            # Pretend we scanned 10 GB by default.
            bytes_processed = 10 * 1024 ** 3
        cost = bytes_processed / (1024 ** 4) * 5.0
        return {
            "query": query,
            "bytes_processed": bytes_processed,
            "estimated_cost_usd": round(cost, 6),
        }


def build_bigquery_connector(config: ConnectorConfig) -> BigQueryConnector:
    return BigQueryConnector(config)
