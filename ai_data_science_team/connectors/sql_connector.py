"""SQLConnector — DataConnector implementation for SQLAlchemy-backed databases (M11).

Any database supported by SQLAlchemy (PostgreSQL, MySQL, SQLite, DuckDB, …) can be
accessed through this connector.  Internally delegates schema introspection to the
existing ``ai_data_science_team.tools.sql.get_database_metadata`` helper.

Example::

    conn = SQLConnector("sqlite:///mydb.sqlite")
    conn.connect()
    logger.info(conn.list_sources())    # ["main.users", "main.orders", ...]
    df = conn.read("main.orders", max_rows=100)
    logger.info(conn.health_check())
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

import pandas as pd

from ai_data_science_team.connectors.base import DataConnector

logger = logging.getLogger(__name__)


class SQLConnector(DataConnector):
    """Read SQL tables as DataFrames via SQLAlchemy.

    Parameters
    ----------
    connection_string:
        SQLAlchemy connection URL, e.g. ``"postgresql+psycopg://user:pass@host/db"``.
    schema:
        Optional schema name to restrict :meth:`list_sources` output.
    connect_args:
        Extra keyword arguments forwarded to ``create_engine``.
    """

    def __init__(
        self,
        connection_string: str,
        *,
        schema: Optional[str] = None,
        query_timeout_seconds: int = 60,
        **connect_args: Any,
    ) -> None:
        self._connection_string = connection_string
        self._schema = schema
        self._query_timeout = query_timeout_seconds
        self._connect_args = connect_args
        self._engine: Any = None  # sqlalchemy.engine.Engine
        self._inspector: Any = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "sql"

    @property
    def description(self) -> str:
        try:
            import sqlalchemy as sa
            safe_url = sa.make_url(self._connection_string).render_as_string(hide_password=True)
        except Exception as e:
            logger.warning("Failed to render safe URL for SQL connector: %s", e)
            safe_url = "<redacted>"
        return f"SQLConnector({safe_url})"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self, **_: Any) -> None:
        with self._lock:
            try:
                import sqlalchemy as sa
            except ImportError as exc:
                raise ImportError(
                    "SQLConnector requires sqlalchemy. Install it with: pip install sqlalchemy"
                ) from exc

            if self._engine is not None:
                try:
                    with self._engine.connect() as c:
                        c.execute(sa.text("SELECT 1"))
                    return
                except Exception as e:
                    logger.warning(
                        "Existing SQL connection validation failed, reconnecting: %s", e
                    )
                    self._engine = None
                    self._inspector = None

            url = sa.make_url(self._connection_string)
            engine_kwargs: Dict[str, Any] = dict(self._connect_args)
            if url.get_backend_name() == "sqlite":
                engine_kwargs.setdefault("connect_args", {})
            else:
                engine_kwargs.setdefault("connect_args", {"connect_timeout": 10})
                engine_kwargs.setdefault("pool_timeout", 30)
                engine_kwargs.setdefault("pool_recycle", 1800)

            self._engine = sa.create_engine(self._connection_string, **engine_kwargs)
            with self._engine.connect() as c:
                c.execute(sa.text("SELECT 1"))
            self._inspector = sa.inspect(self._engine)

    def close(self) -> None:
        with self._lock:
            if self._engine is not None:
                self._engine.dispose()
                self._engine = None
                self._inspector = None

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_sources(self) -> List[str]:
        self._ensure_connected()
        sources: List[str] = []
        schemas = [self._schema] if self._schema else self._inspector.get_schema_names()
        for schema in schemas:
            try:
                for table in self._inspector.get_table_names(schema=schema):
                    sources.append(f"{schema}.{table}")
            except Exception as e:
                logger.warning("Failed to list tables for schema %s: %s", schema, e)
                continue
        return sources

    def get_metadata(self, n_samples: int = 5) -> Dict[str, Any]:
        """Return rich schema metadata (delegates to the existing helper)."""
        self._ensure_connected()
        from ai_data_science_team.tools.sql import get_database_metadata
        return get_database_metadata(self._engine, n_samples=n_samples)

    # ------------------------------------------------------------------
    # Data access
    # ------------------------------------------------------------------

    def read(
        self,
        source: str,
        *,
        max_rows: Optional[int] = None,
        columns: Optional[List[str]] = None,
        where: Optional[str] = None,
        where_params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Read a SQL table into a DataFrame.

        Parameters
        ----------
        source:
            ``"schema.table"`` string as returned by :meth:`list_sources`.
        max_rows:
            LIMIT clause value.
        columns:
            Column selection (``SELECT col1, col2 ...``).
        where:
            Optional WHERE clause with parameterized placeholders, e.g. ``"status = :status"``.
            IMPORTANT: Use named parameters (e.g., :param_name) instead of string interpolation
            to prevent SQL injection. If you must use raw SQL, ensure it's from a trusted source.
        where_params:
            Dictionary of parameter values for the WHERE clause, e.g. ``{"status": "active"}``.
            Required if WHERE clause contains parameterized placeholders.
        """
        self._ensure_connected()
        import sqlalchemy as sa

        if columns:
            validated_columns = [self._validate_identifier(col) for col in columns]
            col_str = ", ".join(validated_columns)
        else:
            col_str = "*"

        preparer = self._engine.dialect.identifier_preparer
        quoted = self._quote_source(source, preparer)

        query = f"SELECT {col_str} FROM {quoted}"
        if where:
            sanitized_where = self._sanitize_where_clause(where)
            query += f" WHERE {sanitized_where}"
        if max_rows is not None:
            if not isinstance(max_rows, int) or max_rows < 0:
                raise ValueError("max_rows must be a non-negative integer")
            query += f" LIMIT {max_rows}"

        with self._engine.connect() as conn:
            conn.execution_options(timeout=self._query_timeout)
            stmt = sa.text(query)
            if where_params:
                stmt = stmt.bindparams(**where_params)
            return pd.read_sql(stmt, conn, **kwargs)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        try:
            self._ensure_connected()
            import sqlalchemy as sa
            with self._engine.connect() as c:
                c.execute(sa.text("SELECT 1"))
            return {
                "connector": self.name,
                "status": "ok",
                "dialect": self._engine.dialect.name,
            }
        except Exception:
            return {
                "connector": self.name,
                "status": "error",
                "error": "Connection failed",
                "error_code": "CONNECTION_ERROR",
            }

    # ------------------------------------------------------------------
    # LangChain integration (richer SQL-aware tools)
    # ------------------------------------------------------------------

    def as_langchain_tools(self) -> list:
        from langchain.tools import tool as lc_tool

        connector = self

        @lc_tool
        def sql_list_tables() -> str:
            """List all tables available in the connected database."""
            sources = connector.list_sources()
            return "\n".join(sources) if sources else "(no tables found)"

        @lc_tool
        def sql_read_table(table: str, max_rows: int = 500) -> str:
            """Read a database table and return its contents as CSV."""
            df = connector.read(table, max_rows=max_rows)
            return df.to_csv(index=False)

        @lc_tool
        def sql_schema() -> str:
            """Return database schema metadata as a JSON string."""
            import json
            meta = connector.get_metadata(n_samples=3)
            return json.dumps(meta, default=str, indent=2)

        return [sql_list_tables, sql_read_table, sql_schema]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_connected(self) -> None:
        if self._engine is None:
            self.connect()

    def _validate_identifier(self, identifier: str) -> str:
        """Validate and quote a SQL identifier (column or table name)."""
        if not identifier or not isinstance(identifier, str):
            raise ValueError("Identifier must be a non-empty string")
        dangerous_chars = [";", "--", "/*", "*/", "'", '"', "\\", "\x00"]
        for char in dangerous_chars:
            if char in identifier:
                raise ValueError(f"Invalid character in identifier: {repr(char)}")
        preparer = self._engine.dialect.identifier_preparer
        return preparer.quote(identifier)

    def _quote_source(self, source: str, preparer: Any) -> str:
        """Quote a source (schema.table or table) safely."""
        if "." in source:
            parts = source.split(".", 1)
            if len(parts) != 2:
                raise ValueError(f"Invalid source format: {source}")
            schema_name, table_name = parts
            return f"{preparer.quote_schema(schema_name)}.{preparer.quote(table_name)}"
        return preparer.quote(source)

    def _sanitize_where_clause(self, where: str) -> str:
        """Validate WHERE clause for safe usage.
        
        SECURITY: This method validates that the WHERE clause contains only
        safe characters and patterns. For user-provided values, ALWAYS use
        where_params parameter for parameterized queries.
        
        Allowed patterns:
        - Column names (alphanumeric + underscore)
        - Comparison operators: =, <>, <, >, <=, >=, !=, LIKE, IN, BETWEEN
        - Logical operators: AND, OR, NOT
        - Parentheses for grouping
        - Parameterized placeholders: :param_name, ?, %s
        - IS NULL, IS NOT NULL
        
        Raises ValueError if potentially dangerous patterns are detected.
        """
        if not where or not isinstance(where, str):
            raise ValueError("WHERE clause must be a non-empty string")
        
        import re
        
        dangerous_patterns = [
            ";", "--", "/*", "*/",
            "DROP", "DELETE", "INSERT", "UPDATE",
            "TRUNCATE", "ALTER", "CREATE", "EXEC", "EXECUTE",
            "xp_", "sp_", "UNION", "INTO", "OUTFILE", "LOAD_FILE"
        ]
        where_upper = where.upper()
        for pattern in dangerous_patterns:
            if pattern in where_upper:
                raise ValueError(f"Potentially dangerous SQL pattern detected: {pattern}")
        
        safe_pattern = re.compile(
            r'^[\w\s\.\,\(\)=<>!\'":\?\%\*\-]+$',
            re.IGNORECASE
        )
        if not safe_pattern.match(where):
            raise ValueError(
                "WHERE clause contains invalid characters. "
                "Only alphanumeric, comparison operators, and placeholders are allowed."
            )
        
        return where
