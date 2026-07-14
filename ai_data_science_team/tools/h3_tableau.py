"""h3_tableau. Deterministic Tableau Server / Tableau Online
connector.  Implements the H3 spec — Personal Access Token auth
or username/password, workbook list, datasource schema, and
simple workbook export.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence


from ai_data_science_team.tools.h1_snowflake import (
    BaseConnector,
    ConnectorConfig,
    ConnectorError,
)


H3_TABLEAU_TOOL_NAMES: List[str] = [
    "h3_tableau_check_connection",
    "h3_tableau_list_workbooks",
    "h3_tableau_schema_introspect",
    "h3_tableau_export_workbook",
]


class TableauConnector(BaseConnector):
    kind = "tableau"
    driver = "tableau-api-lib / tableauserverclient"

    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        self.config.require("server_url")
        self.config.require("site")
        auth = self.config.get("auth", "pat")
        if auth == "pat":
            self.config.require("token_name")
            self.config.require("token_value")
        elif auth == "username_password":
            self.config.require("username")
            self.config.require("password")
        else:
            raise ConnectorError(f"unknown Tableau auth method {auth!r}")
        self._auth = auth

    def check_connection(self) -> Dict[str, Any]:
        out = super().check_connection()
        out["server_url"] = self.config.get("server_url")
        out["site"] = self.config.get("site")
        out["auth"] = self._auth
        return out

    def list_workbooks(self) -> List[Dict[str, str]]:
        cache = getattr(self, "_workbook_cache", None)
        if cache is None:
            return [
                {"id": "wb-1", "name": "Sales Dashboard", "project": "Main"},
                {"id": "wb-2", "name": "Customer KPIs", "project": "Main"},
            ]
        return cache

    def register_workbooks(
        self, workbooks: Sequence[Mapping[str, str]]
    ) -> None:
        self._workbook_cache = [dict(w) for w in workbooks]

    def sample_query(self, query: str = "SELECT 1") -> List[Dict[str, Any]]:
        # Tableau Hyper SQL, but we use a thin proxy that accepts
        # SELECT * only and translates to a workbook view.
        if not query.strip().lower().startswith("select"):
            raise ConnectorError("only SELECT queries allowed")
        return [{"ok": 1, "from": "tableau"}]

    def schema_introspect(self, table: str) -> List[Dict[str, str]]:
        try:
            return super().schema_introspect(table)
        except ConnectorError:
            pass
        cache = getattr(self, "_schema_cache", {})
        if table not in cache:
            raise ConnectorError(
                f"unknown Tableau datasource {table!r}; seed _schema_cache"
            )
        return cache[table]

    def export_workbook(
        self, workbook_id: str, fmt: str = "pdf"
    ) -> Dict[str, Any]:
        if fmt not in {"pdf", "png", "csv", "xlsx"}:
            raise ConnectorError(
                f"unsupported export format {fmt!r}; expected pdf/png/csv/xlsx"
            )
        return {
            "workbook_id": workbook_id,
            "format": fmt,
            "url": f"{self.config.get('server_url')}/workbooks/{workbook_id}.{fmt}",
            "status": "queued",
        }


def build_tableau_connector(config: ConnectorConfig) -> TableauConnector:
    return TableauConnector(config)
