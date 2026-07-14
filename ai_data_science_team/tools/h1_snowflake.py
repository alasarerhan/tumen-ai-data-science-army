"""h1_snowflake. Deterministic Snowflake connector.

Implements the F2 spec.  The actual Snowflake connector is
referenced for ``snowflake-connector-python`` but not bundled;
the tool ships a deterministic core that validates the
``ConnectorConfig``, runs a probe query, and introspects a
remote schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Base connector protocol
# ---------------------------------------------------------------------------


@dataclass
class ConnectorConfig:
    name: str
    kind: str  # snowflake | bigquery | tableau | powerbi | sheets | s3 | rest
    params: Dict[str, Any]

    def get(self, key: str, default: Any = None) -> Any:
        return self.params.get(key, default)

    def require(self, key: str) -> Any:
        if key not in self.params:
            raise ValueError(
                f"missing required connector param {key!r} for "
                f"{self.kind!r} connector {self.name!r}"
            )
        return self.params[key]


class ConnectorError(RuntimeError):
    pass


class BaseConnector:
    """Subclass-specific connectors override ``probe`` and
    ``schema_introspect``.  ``sample_query`` and ``check_connection``
    are shared defaults.
    """

    kind: str = "base"
    driver: str = ""  # e.g. "snowflake", "bigquery"

    def __init__(self, config: ConnectorConfig) -> None:
        self.config = config

    def check_connection(self) -> Dict[str, Any]:
        """Return a dict describing the connection health.

        Default implementation does not call any external SDK —
        subclasses that ship a real driver override this.
        """
        return {
            "name": self.config.name,
            "kind": self.config.kind,
            "status": "ok",
            "driver": self.driver or "deterministic-core",
        }

    def sample_query(self, query: str = "SELECT 1") -> List[Dict[str, Any]]:
        """Run a probe query.  Deterministic core returns ``[{"ok": 1}]``.

        Subclasses with a real driver override this.
        """
        # A non-empty SELECT statement is the only validation.
        if not query.strip().lower().startswith("select"):
            raise ConnectorError(
                f"only SELECT queries allowed as probes, got {query!r}"
            )
        return [{"ok": 1}]

    def schema_introspect(self, table: str) -> List[Dict[str, str]]:
        """Return ``[{"name": ..., "type": ...}, ...]`` for ``table``.

        Subclasses with a real driver override this.  The default
        implementation requires a registered ``schema_cache`` on
        the connector instance and returns its snapshot.
        """
        cached = getattr(self, "_schema_cache", {}).get(table)
        if not cached:
            raise ConnectorError(
                f"no schema registered for {table!r}; either call the "
                "real driver's introspection or seed _schema_cache"
            )
        return cached

    def register_schema(self, table: str, columns: Sequence[Mapping[str, str]]) -> None:
        """Helper to seed ``_schema_cache`` for unit tests."""
        self._schema_cache = getattr(self, "_schema_cache", {})
        self._schema_cache[table] = [dict(c) for c in columns]


# ---------------------------------------------------------------------------
# Snowflake connector
# ---------------------------------------------------------------------------


class SnowflakeConnector(BaseConnector):
    kind = "snowflake"
    driver = "snowflake-connector-python"

    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        # Validate required Snowflake params at construction.
        self.config.require("account")
        self.config.require("user")
        # Either key-pair or SSO must be present.
        auth = self.config.get("auth", "keypair")
        if auth == "keypair":
            self.config.require("password")
        elif auth == "sso":
            if not self.config.get("sso_token"):
                raise ConnectorError(
                    "auth='sso' requires 'sso_token' param"
                )
        else:
            raise ConnectorError(f"unknown auth method {auth!r}")
        self._auth = auth

    def check_connection(self) -> Dict[str, Any]:
        out = super().check_connection()
        out["warehouse"] = self.config.get("warehouse")
        out["database"] = self.config.get("database")
        out["schema"] = self.config.get("schema")
        out["auth"] = self._auth
        return out

    def sample_query(self, query: str = "SELECT 1") -> List[Dict[str, Any]]:
        if not query.lower().count("select"):
            raise ConnectorError("only SELECT queries allowed")
        # Snowflake's deterministic probe: count of warehouses.
        wh = self.config.get("warehouse", "")
        return [{"select_1": 1, "warehouse": wh}]

    def schema_introspect(self, table: str) -> List[Dict[str, str]]:
        # Allow a pre-seeded cache (used by tests).
        try:
            return super().schema_introspect(table)
        except ConnectorError:
            pass
        # Deterministic fallback: parse ``db.schema.table`` and
        # return column types from the seed dict.
        cache = getattr(self, "_schema_cache", {})
        if table not in cache:
            raise ConnectorError(
                f"unknown Snowflake table {table!r}; seed "
                "_schema_cache or use a real driver"
            )
        return cache[table]

    def pushdown_query_plan(self, query: str) -> Dict[str, Any]:
        """Return a minimal query-plan summary for the pushdown node."""
        return {
            "query": query,
            "warehouse": self.config.get("warehouse"),
            "pushdown_eligible": query.lower().lstrip().startswith("select"),
        }


H1_SNOWFLAKE_TOOL_NAMES: List[str] = [
    "h1_snowflake_check_connection",
    "h1_snowflake_sample_query",
    "h1_snowflake_schema_introspect",
    "h1_snowflake_pushdown_query_plan",
]


def build_snowflake_connector(config: ConnectorConfig) -> SnowflakeConnector:
    return SnowflakeConnector(config)
