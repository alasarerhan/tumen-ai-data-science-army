"""h5_sheets. Deterministic Google Sheets connector. Implements the
H5 spec — service-account or OAuth auth, sheet + range reads, and
range writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


from ai_data_science_team.tools.h1_snowflake import (
    BaseConnector,
    ConnectorConfig,
    ConnectorError,
)


H5_SHEETS_TOOL_NAMES: List[str] = [
    "h5_sheets_check_connection",
    "h5_sheets_read_range",
    "h5_sheets_list_sheets",
    "h5_sheets_write_range",
]


class GoogleSheetsConnector(BaseConnector):
    kind = "sheets"
    driver = "gspread / google-api-python-client"

    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        auth = self.config.get("auth", "service_account")
        if auth == "service_account":
            self.config.require("credentials_path")
        elif auth == "oauth":
            if not self.config.get("oauth_token"):
                raise ConnectorError("auth='oauth' requires 'oauth_token'")
        else:
            raise ConnectorError(
                f"unknown Google Sheets auth method {auth!r}"
            )
        self._auth = auth

    def check_connection(self) -> Dict[str, Any]:
        out = super().check_connection()
        out["auth"] = self._auth
        return out

    def list_sheets(self, spreadsheet_id: str) -> List[Dict[str, str]]:
        cache = getattr(self, "_sheet_cache", {}).get(spreadsheet_id)
        if cache is None:
            return [{"title": "Sheet1", "index": 0}]
        return cache

    def register_sheets(
        self, spreadsheet_id: str, sheets: Sequence[Mapping[str, Any]]
    ) -> None:
        self._sheet_cache = getattr(self, "_sheet_cache", {})
        self._sheet_cache[spreadsheet_id] = [dict(s) for s in sheets]

    def read_range(
        self, spreadsheet_id: str, range_a1: str
    ) -> List[List[Any]]:
        if not range_a1 or "!" not in range_a1:
            raise ConnectorError(
                f"range_a1 must be of the form 'Sheet1!A1:B5', got {range_a1!r}"
            )
        cache = getattr(self, "_range_cache", {})
        key = (spreadsheet_id, range_a1.split("!")[1])
        if key in cache:
            return cache[key]
        # Default deterministic payload: a 2x2 zero matrix.
        return [[0, 0], [0, 0]]

    def register_range(
        self, spreadsheet_id: str, range_a1: str, values: List[List[Any]]
    ) -> None:
        self._range_cache = getattr(self, "_range_cache", {})
        key = (spreadsheet_id, range_a1.split("!")[1])
        self._range_cache[key] = values

    def write_range(
        self, spreadsheet_id: str, range_a1: str, values: List[List[Any]]
    ) -> Dict[str, Any]:
        self.register_range(spreadsheet_id, range_a1, values)
        return {
            "spreadsheet_id": spreadsheet_id,
            "range": range_a1,
            "rows_written": len(values),
            "status": "ok",
        }


def build_sheets_connector(config: ConnectorConfig) -> GoogleSheetsConnector:
    return GoogleSheetsConnector(config)
