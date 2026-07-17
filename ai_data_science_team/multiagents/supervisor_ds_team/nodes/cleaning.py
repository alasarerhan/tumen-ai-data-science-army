from __future__ import annotations

"""Auto-generated cleaning node module.

Extracted from the 3,400-line ``supervisor_ds_team.py`` monolith
during the L2 code-review remediation pass.  Uses dependency
injection via the ``CleaningNodeDeps`` dataclass.
"""

import logging  # noqa: E402, F401
from dataclasses import dataclass  # noqa: E402, F401
from typing import Any, Callable  # noqa: E402, F401

from langchain_core.messages import AIMessage  # noqa: E402, F401

from ai_data_science_team.multiagents.supervisor import (  # noqa: E402, F401
    SupervisorDSState,
    append_agent_feedback,
    register_python_transform_dataset)

logger = logging.getLogger(__name__)


@dataclass
class CleaningNodeDeps:
    """Dependencies for the cleaning node."""
    data_cleaning_agent: Any
    ensure_dataset_registry: Any  # was _ensure_dataset_registry
    ensure_df: Any  # was _ensure_df
    format_result_with_llm: Any  # was _format_result_with_llm
    get_active_data: Any  # was _get_active_data
    _get_last_human_text: Any  # was _get_last_human
    is_empty_df: Any  # was _is_empty_df
    merge_messages: Any  # was _merge_messages
    tag_messages: Any  # was _tag_messages
    llm: Any


def make_node_cleaning(deps: CleaningNodeDeps) -> Callable[[SupervisorDSState], dict]:
    """Build the ``node_cleaning`` state-graph node."""

    def node_cleaning(state: SupervisorDSState):
        logger.info("---DATA CLEANING---")
        before_msgs = list(state.get("messages", []) or [])
        last_human = deps._get_last_human_text(before_msgs)
        datasets, active_dataset_id = deps.ensure_dataset_registry(state)
        state_with_datasets = {  # type: ignore[typeddict-item]
            **{k: v for k, v in (state or {}).items()},  # type: ignore[typeddict-item]
            "datasets": datasets,
            "active_dataset_id": active_dataset_id,
        }
        active_df = deps.ensure_df(
            deps.get_active_data(
                state_with_datasets,  # type: ignore[arg-type]
                [
                    "data_wrangled",
                    "data_raw",
                    "data_sql",
                    "data_cleaned",
                    "feature_data",
                ])
        )
        if deps.is_empty_df(active_df):
            return {
                "messages": [
                    AIMessage(
                        content="No dataset is available to clean. Load a file (or run a SQL query) first.",
                        name="data_cleaning_agent")
                ],
                "last_worker": "Data_Cleaning_Agent",
            }
        deps.data_cleaning_agent.invoke_messages(
            messages=before_msgs,
            user_instructions=last_human,
            data_raw=active_df)
        response = deps.data_cleaning_agent.response or {}
        merged = deps.merge_messages(before_msgs, response)
        merged["messages"] = deps.tag_messages(
            merged.get("messages"), "data_cleaning_agent"
        )
        append_agent_feedback(
            merged,
            agent_name="data_cleaning_agent",
            summary_data=response.get("data_cleaned"),
            last_human=deps._get_last_human_text(before_msgs),
            format_result_with_llm=deps.format_result_with_llm,
            extra_text="Cleaning/imputation completed.",
            error_text=response.get("data_cleaner_error"),
            error_log_path=response.get("data_cleaner_error_log_path"),
            error_prefix="Data cleaning error")
        data_cleaned = response.get("data_cleaned")
        if data_cleaned is not None:
            try:
                datasets, active_dataset_id, _did = register_python_transform_dataset(
                    state_with_datasets=state_with_datasets,  # type: ignore[arg-type]
                    data=data_cleaned,
                    stage="cleaned",
                    label="data_cleaned",
                    created_by="Data_Cleaning_Agent",
                    user_request=last_human,
                    function_code=response.get("data_cleaner_function"),
                    function_name=response.get("data_cleaner_function_name"),
                    function_path=response.get("data_cleaner_function_path"),
                    recommended_steps=response.get("recommended_steps"),
                    parent_id=active_dataset_id,
                    error_text=response.get("data_cleaner_error"),
                    error_log_path=response.get("data_cleaner_error_log_path"),
                    summary=response.get("data_cleaning_summary"))
            except Exception:
                pass
        downstream_resets = (
            {
                "eda_artifacts": None,
                "viz_graph": None,
                "feature_data": None,
                "model_info": None,
                "mlflow_artifacts": None,
            }
            if data_cleaned is not None
            else {}
        )
        return {
            **merged,
            "data_cleaned": data_cleaned,
            "active_data_key": "data_cleaned"
            if data_cleaned is not None
            else state.get("active_data_key"),
            "datasets": datasets,
            "active_dataset_id": active_dataset_id,
            "artifacts": {
                **state.get("artifacts", {}),
                "data_cleaning": data_cleaned,
                "data_cleaning_details": {
                    "data_cleaner_function": response.get("data_cleaner_function"),
                    "data_cleaner_function_path": response.get(
                        "data_cleaner_function_path"
                    ),
                    "data_cleaner_function_name": response.get(
                        "data_cleaner_function_name"
                    ),
                    "data_cleaner_error": response.get("data_cleaner_error"),
                    "data_cleaner_error_log_path": response.get(
                        "data_cleaner_error_log_path"
                    ),
                    "data_cleaning_summary": response.get("data_cleaning_summary"),
                    "recommended_steps": response.get("recommended_steps"),
                },
            },
            "last_worker": "Data_Cleaning_Agent",
            **downstream_resets,
        }


    return node_cleaning



__all__ = ["CleaningNodeDeps", "make_node_cleaning"]
