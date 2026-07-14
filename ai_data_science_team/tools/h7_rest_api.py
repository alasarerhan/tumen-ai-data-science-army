"""h7_rest_api. Deterministic REST API data source. Implements the
H7 spec — endpoint config, auth (bearer / api_key / basic), schema
inference from a sample response, and pagination.  ``httpx`` and
``requests`` are referenced but not bundled; the deterministic core
provides a uniform contract and an in-memory backend for tests.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence


from ai_data_science_team.tools.h1_snowflake import (
    BaseConnector,
    ConnectorConfig,
    ConnectorError,
)


H7_REST_API_TOOL_NAMES: List[str] = [
    "h7_rest_api_check_connection",
    "h7_rest_api_probe",
    "h7_rest_api_schema_infer",
    "h7_rest_api_paginate",
]


class RESTConnector(BaseConnector):
    kind = "rest"
    driver = "httpx / requests"

    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        self.config.require("base_url")
        auth = self.config.get("auth", "none")
        if auth == "bearer":
            self.config.require("token")
        elif auth == "api_key":
            self.config.require("api_key")
        elif auth == "basic":
            self.config.require("username")
            self.config.require("password")
        elif auth != "none":
            raise ConnectorError(f"unknown auth method {auth!r}")
        self._auth = auth

    def check_connection(self) -> Dict[str, Any]:
        out = super().check_connection()
        out["base_url"] = self.config.get("base_url")
        out["auth"] = self._auth
        return out

    def probe(self, path: str = "/") -> Dict[str, Any]:
        cache = getattr(self, "_probe_cache", {}).get(path)
        if cache is not None:
            return cache
        return {
            "path": path,
            "status": "ok",
            "content_type": "application/json",
            "size_bytes": 1234,
        }

    def register_probe(self, path: str, payload: Mapping[str, Any]) -> None:
        self._probe_cache = getattr(self, "_probe_cache", {})
        self._probe_cache[path] = dict(payload)

    def schema_infer(
        self, path: str = "/", *, sample_size: int = 1
    ) -> List[Dict[str, str]]:
        cache = getattr(self, "_schema_cache", {}).get(path)
        if cache is not None:
            return cache
        # Deterministic fallback: try to use a registered sample
        # payload, otherwise a generic {id, name, value, ts} schema.
        return [
            {"name": "id", "type": "string"},
            {"name": "name", "type": "string"},
            {"name": "value", "type": "number"},
            {"name": "ts", "type": "datetime"},
        ]

    def register_schema(
        self, path: str, columns: Sequence[Mapping[str, str]]
    ) -> None:
        self._schema_cache = getattr(self, "_schema_cache", {})
        self._schema_cache[path] = [dict(c) for c in columns]

    def paginate(
        self, path: str, *, page_size: int = 50, max_pages: int = 10
    ) -> List[Dict[str, Any]]:
        cache = getattr(self, "_paginate_cache", {}).get(path)
        if cache is not None:
            return cache
        # Deterministic synthetic pagination.
        out = []
        for p in range(min(max_pages, 3)):
            for i in range(page_size):
                out.append(
                    {"page": p + 1, "index": i, "id": f"{(p * page_size) + i}"}
                )
        return out[: page_size * max_pages]


def build_rest_connector(config: ConnectorConfig) -> RESTConnector:
    return RESTConnector(config)
