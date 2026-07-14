"""Database tools for the AI Data Science Team.

This module provides tools for database introspection, query generation,
and SQL execution. These tools are used by SQLDatabaseAgent and other
database-related agents.

Tools
-----
- introspect_schema: Get database metadata (tables, columns, types)
- sample_table: Get sample rows from a table
- execute_sql: Execute a SQL query and return results
- validate_sql_safety: Check for destructive operations
- build_sample_query: Build dialect-specific sample query
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Union

import pandas as pd
import sqlalchemy as sql
from sqlalchemy import inspect

from ai_data_science_team.tool_registry import (
    ToolParameter,
    register_tool,
)


@register_tool(
    name="introspect_schema",
    description="Get database metadata including tables, columns, types, primary keys, and foreign keys.",
    parameters={
        "connection": ToolParameter(type="object", description="SQLAlchemy connection or engine", required=True),
        "n_samples": ToolParameter(type="integer", description="Number of sample values per column", required=False, default=10),
    },
    returns="Dict with database metadata",
    namespace="core.database",
    capabilities=["database", "schema", "introspection", "metadata"],
    cost_tier="medium",
)
def introspect_schema(connection: Union[sql.engine.base.Connection, sql.engine.base.Engine], n_samples: int = 10) -> dict:
    """Get database metadata including tables, columns, types, and relationships.

    Parameters
    ----------
    connection : SQLAlchemy Connection or Engine
        The database connection.
    n_samples : int
        Number of sample values to retrieve for each column.

    Returns
    -------
    dict
        Database metadata with schemas, tables, columns, and sample data.
    """
    is_engine = isinstance(connection, sql.engine.base.Engine)
    conn = connection.connect() if is_engine else connection

    metadata: Dict[str, Any] = {
        "dialect": None,
        "driver": None,
        "connection_url": None,
        "schemas": [],
    }

    try:
        sql_engine = conn.engine
        dialect_name = sql_engine.dialect.name.lower()

        metadata["dialect"] = sql_engine.dialect.name
        metadata["driver"] = sql_engine.driver
        try:
            metadata["connection_url"] = sql_engine.url.render_as_string(hide_password=True)
        except Exception:
            metadata["connection_url"] = str(sql_engine.url)

        inspector = inspect(sql_engine)
        preparer = inspector.bind.dialect.identifier_preparer

        for schema_name in inspector.get_schema_names():
            schema_obj = {"schema_name": schema_name, "tables": []}

            tables = inspector.get_table_names(schema=schema_name)
            for table_name in tables:
                table_info = {
                    "table_name": table_name,
                    "columns": [],
                    "primary_key": [],
                    "foreign_keys": [],
                    "indexes": [],
                }

                columns = inspector.get_columns(table_name, schema=schema_name)
                for col in columns:
                    col_name = col["name"]
                    col_type = str(col["type"])
                    table_name_quoted = f"{preparer.quote_identifier(schema_name)}.{preparer.quote_identifier(table_name)}"
                    col_name_quoted = preparer.quote_identifier(col_name)

                    query = build_sample_query(col_name_quoted, table_name_quoted, n_samples, dialect_name)

                    try:
                        df = pd.read_sql(query, conn)
                        samples = df[col_name].head(n_samples).tolist()
                    except Exception as e:
                        samples = [f"Error retrieving data: {str(e)}"]

                    table_info["columns"].append({
                        "name": col_name,
                        "type": col_type,
                        "sample_values": samples,
                    })

                pk_constraint = inspector.get_pk_constraint(table_name, schema=schema_name)
                table_info["primary_key"] = pk_constraint.get("constrained_columns", [])

                fks = inspector.get_foreign_keys(table_name, schema=schema_name)
                table_info["foreign_keys"] = [
                    {
                        "local_cols": fk["constrained_columns"],
                        "referred_table": fk["referred_table"],
                        "referred_cols": fk["referred_columns"],
                    }
                    for fk in fks
                ]

                idxs = inspector.get_indexes(table_name, schema=schema_name)
                table_info["indexes"] = idxs

                schema_obj["tables"].append(table_info)

            metadata["schemas"].append(schema_obj)

    finally:
        if is_engine:
            conn.close()

    return metadata


@register_tool(
    name="sample_table",
    description="Get sample rows from a database table.",
    parameters={
        "connection": ToolParameter(type="object", description="SQLAlchemy connection or engine", required=True),
        "table_name": ToolParameter(type="string", description="Table name to sample", required=True),
        "schema": ToolParameter(type="string", description="Schema name (if applicable)", required=False),
        "n_rows": ToolParameter(type="integer", description="Number of rows to sample", required=False, default=100),
    },
    returns="DataFrame as dict",
    namespace="core.database",
    capabilities=["database", "sample", "preview"],
    cost_tier="low",
)
def sample_table(
    connection: Union[sql.engine.base.Connection, sql.engine.base.Engine],
    table_name: str,
    schema: Optional[str] = None,
    n_rows: int = 100,
) -> dict:
    """Get sample rows from a database table.

    Parameters
    ----------
    connection : SQLAlchemy Connection or Engine
        The database connection.
    table_name : str
        Table name to sample.
    schema : str, optional
        Schema name if applicable.
    n_rows : int
        Number of rows to sample.

    Returns
    -------
    dict
        DataFrame as dictionary.
    """
    is_engine = isinstance(connection, sql.engine.base.Engine)
    conn = connection.connect() if is_engine else connection

    try:
        sql_engine = conn.engine
        dialect_name = sql_engine.dialect.name.lower()
        inspector = inspect(sql_engine)
        preparer = inspector.bind.dialect.identifier_preparer

        if schema:
            full_table = f"{preparer.quote_identifier(schema)}.{preparer.quote_identifier(table_name)}"
        else:
            full_table = preparer.quote_identifier(table_name)

        if "postgres" in dialect_name or "sqlite" in dialect_name:
            query = f"SELECT * FROM {full_table} ORDER BY RANDOM() LIMIT {n_rows}"
        elif "mysql" in dialect_name:
            query = f"SELECT * FROM {full_table} ORDER BY RAND() LIMIT {n_rows}"
        elif "mssql" in dialect_name:
            query = f"SELECT TOP {n_rows} * FROM {full_table} ORDER BY NEWID()"
        else:
            query = f"SELECT * FROM {full_table} WHERE ROWNUM <= {n_rows}"

        df = pd.read_sql(query, conn)
        return df.to_dict()

    finally:
        if is_engine:
            conn.close()


@register_tool(
    name="execute_sql",
    description="Execute a SQL query and return results as a DataFrame.",
    parameters={
        "connection": ToolParameter(type="object", description="SQLAlchemy connection or engine", required=True),
        "query": ToolParameter(type="string", description="SQL query to execute", required=True),
    },
    returns="DataFrame as dict",
    namespace="core.database",
    capabilities=["database", "query", "execute"],
    cost_tier="low",
)
def execute_sql(
    connection: Union[sql.engine.base.Connection, sql.engine.base.Engine],
    query: str,
) -> dict:
    """Execute a SQL query and return results.

    Parameters
    ----------
    connection : SQLAlchemy Connection or Engine
        The database connection.
    query : str
        SQL query to execute.

    Returns
    -------
    dict
        DataFrame as dictionary.
    """
    is_engine = isinstance(connection, sql.engine.base.Engine)
    conn = connection.connect() if is_engine else connection

    try:
        df = pd.read_sql(query, conn)
        return df.to_dict()
    finally:
        if is_engine:
            conn.close()


@register_tool(
    name="validate_sql_safety",
    description="Check if a SQL query contains destructive operations (INSERT, UPDATE, DELETE, DROP, etc.).",
    parameters={
        "query": ToolParameter(type="string", description="SQL query to validate", required=True),
        "allow_insert": ToolParameter(type="boolean", description="Allow INSERT statements", required=False, default=False),
        "allow_update": ToolParameter(type="boolean", description="Allow UPDATE statements", required=False, default=False),
        "allow_delete": ToolParameter(type="boolean", description="Allow DELETE statements", required=False, default=False),
    },
    returns="Dict with is_safe boolean and reason string",
    namespace="core.database",
    capabilities=["database", "safety", "validation"],
    cost_tier="low",
)
def validate_sql_safety(
    query: str,
    allow_insert: bool = False,
    allow_update: bool = False,
    allow_delete: bool = False,
) -> dict:
    """Validate SQL query for safety.

    Parameters
    ----------
    query : str
        SQL query to validate.
    allow_insert : bool
        Allow INSERT statements.
    allow_update : bool
        Allow UPDATE statements.
    allow_delete : bool
        Allow DELETE statements.

    Returns
    -------
    dict
        {is_safe: bool, reason: str}
    """
    query_upper = query.upper().strip()

    dangerous_patterns = [
        (r"\bDROP\b", "DROP statements are not allowed"),
        (r"\bTRUNCATE\b", "TRUNCATE statements are not allowed"),
        (r"\bALTER\b", "ALTER statements are not allowed"),
        (r"\bCREATE\b", "CREATE statements are not allowed"),
        (r"\bGRANT\b", "GRANT statements are not allowed"),
        (r"\bREVOKE\b", "REVOKE statements are not allowed"),
        (r"\bEXEC\b", "EXEC statements are not allowed"),
        (r"\bEXECUTE\b", "EXECUTE statements are not allowed"),
        (r"\bXP_\w+", "Extended stored procedures are not allowed"),
        (r"\bSP_\w+", "System stored procedures are not allowed"),
    ]

    if not allow_insert:
        dangerous_patterns.append((r"\bINSERT\b", "INSERT statements are not allowed"))
    if not allow_update:
        dangerous_patterns.append((r"\bUPDATE\b", "UPDATE statements are not allowed"))
    if not allow_delete:
        dangerous_patterns.append((r"\bDELETE\b", "DELETE statements are not allowed"))

    for pattern, reason in dangerous_patterns:
        if re.search(pattern, query_upper):
            return {"is_safe": False, "reason": reason}

    return {"is_safe": True, "reason": "Query is safe"}


def build_sample_query(col_name_quoted: str, table_name_quoted: str, n: int, dialect_name: str) -> str:
    """Build a dialect-specific sample query.

    Parameters
    ----------
    col_name_quoted : str
        Quoted column name.
    table_name_quoted : str
        Quoted table name.
    n : int
        Number of rows to sample.
    dialect_name : str
        Database dialect name.

    Returns
    -------
    str
        SQL query string.
    """
    if "postgres" in dialect_name:
        return f"SELECT {col_name_quoted} FROM {table_name_quoted} ORDER BY RANDOM() LIMIT {n}"
    if "mysql" in dialect_name:
        return f"SELECT {col_name_quoted} FROM {table_name_quoted} ORDER BY RAND() LIMIT {n}"
    if "sqlite" in dialect_name:
        return f"SELECT {col_name_quoted} FROM {table_name_quoted} ORDER BY RANDOM() LIMIT {n}"
    if "mssql" in dialect_name:
        return f"SELECT TOP {n} {col_name_quoted} FROM {table_name_quoted} ORDER BY NEWID()"
    return f"SELECT {col_name_quoted} FROM {table_name_quoted} WHERE ROWNUM <= {n}"


DATABASE_TOOLS = [
    "introspect_schema",
    "sample_table",
    "execute_sql",
    "validate_sql_safety",
]


__all__ = [
    "introspect_schema",
    "sample_table",
    "execute_sql",
    "validate_sql_safety",
    "build_sample_query",
    "DATABASE_TOOLS",
]
