from __future__ import annotations

from pathlib import Path
from typing import Any

import sqlalchemy as sa

from ai_data_science_team.templates.agent_templates import (
    node_func_execute_agent_from_sql_connection,
)


def _orders_engine(tmp_path: Path) -> sa.Engine:
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'orders.db'}")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE orders (id INTEGER PRIMARY KEY, amount REAL)"))
        conn.execute(sa.text("INSERT INTO orders (id, amount) VALUES (1, 10.5), (2, 20.25)"))
    return engine


def _execute_sql_agent(state: dict[str, Any], engine: sa.Engine) -> dict[str, Any]:
    return node_func_execute_agent_from_sql_connection(
        state=state,
        connection=engine,
        code_snippet_key="sql_database_function",
        result_key="data_sql",
        error_key="sql_database_error",
        agent_function_name="sql_database_pipeline",
        post_processing=lambda df: df.to_dict(orient="list"),
        error_message_prefix="SQL agent failed: ",
    )


def test_sql_agent_executes_query_without_dynamic_python_exec(tmp_path: Path) -> None:
    engine = _orders_engine(tmp_path)
    state = {
        "sql_query_code": "SELECT id, amount FROM orders ORDER BY id",
        "sql_database_function": """
raise RuntimeError("dynamic exec should not run")

def sql_database_pipeline(connection):
    raise RuntimeError("dynamic function should not run")
""",
    }

    result = _execute_sql_agent(state, engine)

    assert result["sql_database_error"] is None
    assert result["data_sql"] == {"id": [1, 2], "amount": [10.5, 20.25]}


def test_sql_agent_extracts_legacy_static_query_without_exec(tmp_path: Path) -> None:
    engine = _orders_engine(tmp_path)
    state = {
        "sql_database_function": """
def sql_database_pipeline(connection):
    sql_query = '''
    SELECT id FROM orders ORDER BY id
    '''.strip()
    raise RuntimeError("dynamic function should not run")
""",
    }

    result = _execute_sql_agent(state, engine)

    assert result["sql_database_error"] is None
    assert result["data_sql"] == {"id": [1, 2]}


def test_sql_agent_rejects_destructive_sql_before_database_execution(tmp_path: Path) -> None:
    engine = _orders_engine(tmp_path)
    state = {
        "sql_query_code": "DROP TABLE orders",
        "sql_database_function": """
def sql_database_pipeline(connection):
    return None
""",
    }

    result = _execute_sql_agent(state, engine)

    assert result["data_sql"] is None
    assert (
        result["sql_database_error"]
        == "SQL agent failed: Only read-only SELECT queries are allowed."
    )

    with engine.connect() as conn:
        count = conn.execute(sa.text("SELECT COUNT(*) FROM orders")).scalar_one()
    assert count == 2
