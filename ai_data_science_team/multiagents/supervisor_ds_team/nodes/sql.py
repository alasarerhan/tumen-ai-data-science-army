from __future__ import annotations

"""Auto-generated sql node module.

Extracted from the 3,400-line ``supervisor_ds_team.py`` monolith
during the L2 code-review remediation pass.  Uses dependency
injection via the ``SqlNodeDeps`` dataclass.
"""

import logging  # noqa: E402, F401
from dataclasses import dataclass  # noqa: E402, F401
from typing import Any, Callable  # noqa: E402, F401

from langchain_core.messages import AIMessage  # noqa: E402, F401

from ai_data_science_team.multiagents.supervisor import (  # noqa: E402, F401
    SupervisorDSState)

logger = logging.getLogger(__name__)


@dataclass
class SqlNodeDeps:
    """Dependencies for the sql node."""
    sql_database_agent: Any
    append_error_message: Any  # was _append_error_message
    ensure_dataset_registry: Any  # was _ensure_dataset_registry
    format_result_with_llm: Any  # was _format_result_with_llm
    _get_last_human_text: Any  # was _get_last_human
    merge_messages: Any  # was _merge_messages
    register_dataset: Any  # was _register_dataset
    sha256_text: Any  # was _sha256_text
    tag_messages: Any  # was _tag_messages
    truncate_text: Any  # was _truncate_text
    llm: Any


def make_node_sql(deps: SqlNodeDeps) -> Callable[[SupervisorDSState], dict]:
    """Build the ``node_sql`` state-graph node."""

    def node_sql(state: SupervisorDSState):
        logger.info("---SQL DATABASE---")
        before_msgs = list(state.get("messages", []) or [])
        last_human = deps._get_last_human_text(before_msgs)
        datasets, active_dataset_id = deps.ensure_dataset_registry(state)
        deps.sql_database_agent.invoke_messages(
            messages=before_msgs,
            user_instructions=last_human)
        response = deps.sql_database_agent.response or {}
        merged = deps.merge_messages(before_msgs, response)
        merged["messages"] = deps.tag_messages(merged.get("messages"), "sql_database_agent")
        summary_text = deps.format_result_with_llm(
            "sql_database_agent",
            response.get("data_sql"),
            deps._get_last_human_text(before_msgs),
            extra_text=response.get("sql_query_code", ""))
        if summary_text:
            merged["messages"].append(
                AIMessage(content=summary_text, name="sql_database_agent")
            )
        deps.append_error_message(
            merged,
            "sql_database_agent",
            response.get("sql_database_error"),
            response.get("sql_database_error_log_path"),
            prefix="SQL error")
        data_sql = response.get("data_sql")
        if data_sql is not None:
            try:
                sql_code_full = response.get("sql_query_code")
                sql_code_hash = deps.sha256_text(sql_code_full)
                sql_code = deps.truncate_text(sql_code_full, 12000)
                sql_fn_full = response.get("sql_database_function")
                sql_fn_hash = deps.sha256_text(sql_fn_full)
                sql_fn = deps.truncate_text(sql_fn_full, 6000)
                datasets, active_dataset_id, _did = deps.register_dataset(
                    {
                        **state,
                        "datasets": datasets,
                        "active_dataset_id": active_dataset_id,
                    },
                    data=data_sql,
                    stage="sql",
                    label="data_sql",
                    created_by="SQL_Database_Agent",
                    provenance={
                        "source_type": "sql",
                        "user_request": last_human,
                        "transform": {
                            "kind": "sql_query",
                            "sql_query_code": sql_code,
                            "sql_sha256": sql_code_hash,
                            "sql_database_function": sql_fn,
                            "sql_database_function_sha256": sql_fn_hash,
                            "sql_database_function_path": response.get(
                                "sql_database_function_path"
                            ),
                            "sql_database_function_name": response.get(
                                "sql_database_function_name"
                            ),
                        },
                    },
                    parent_id=None,
                    make_active=True)
            except Exception:
                pass
        return {
            **merged,
            "data_sql": data_sql,
            "active_data_key": "data_sql"
            if data_sql is not None
            else state.get("active_data_key"),
            "datasets": datasets,
            "active_dataset_id": active_dataset_id,
            "artifacts": {
                **state.get("artifacts", {}),
                "sql": {
                    "sql_query_code": response.get("sql_query_code"),
                    "sql_database_function": response.get("sql_database_function"),
                    "sql_database_function_path": response.get(
                        "sql_database_function_path"
                    ),
                    "sql_database_function_name": response.get(
                        "sql_database_function_name"
                    ),
                    "sql_database_error": response.get("sql_database_error"),
                    "sql_database_error_log_path": response.get(
                        "sql_database_error_log_path"
                    ),
                    "recommended_steps": response.get("recommended_steps"),
                    "data_sql": data_sql,
                },
            },
            "last_worker": "SQL_Database_Agent",
        }


    return node_sql



__all__ = ["SqlNodeDeps", "make_node_sql"]
