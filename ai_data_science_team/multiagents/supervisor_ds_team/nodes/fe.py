from __future__ import annotations

"""Auto-generated fe node module.

Extracted from the 3,400-line ``supervisor_ds_team.py`` monolith
during the L2 code-review remediation pass.  Uses dependency
injection via the ``FeNodeDeps`` dataclass.
"""

import logging  # noqa: E402, F401
from dataclasses import dataclass  # noqa: E402, F401
from typing import Any, Callable  # noqa: E402, F401

from langchain_core.messages import AIMessage  # noqa: E402, F401

from ai_data_science_team.multiagents.supervisor import (  # noqa: E402, F401
    SupervisorDSState,
    append_agent_feedback,
    register_python_transform_dataset,
)

logger = logging.getLogger(__name__)


@dataclass
class FeNodeDeps:
    """Dependencies for the fe node."""

    feature_engineering_agent: Any
    ensure_dataset_registry: Any  # was _ensure_dataset_registry
    ensure_df: Any  # was _ensure_df
    format_result_with_llm: Any  # was _format_result_with_llm
    get_active_data: Any  # was _get_active_data
    _get_last_human_text: Any  # was _get_last_human
    is_empty_df: Any  # was _is_empty_df
    merge_messages: Any  # was _merge_messages
    tag_messages: Any  # was _tag_messages
    llm: Any


def make_node_fe(deps: FeNodeDeps) -> Callable[[SupervisorDSState], dict]:
    """Build the ``node_fe`` state-graph node."""

    def node_fe(state: SupervisorDSState):
        logger.info("---FEATURE ENGINEERING---")
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
                    "data_cleaned",
                    "data_wrangled",
                    "data_sql",
                    "data_raw",
                    "feature_data",
                ],
            )
        )
        if deps.is_empty_df(active_df):
            return {
                "messages": [
                    AIMessage(
                        content="No dataset is available for feature engineering. Load a file (or run a SQL query) first.",
                        name="feature_engineering_agent",
                    )
                ],
                "last_worker": "Feature_Engineering_Agent",
            }
        deps.feature_engineering_agent.invoke_messages(
            messages=before_msgs,
            user_instructions=last_human,
            data_raw=active_df,
            target_variable=state.get("target_variable"),
        )
        response = deps.feature_engineering_agent.response or {}
        merged = deps.merge_messages(before_msgs, response)
        merged["messages"] = deps.tag_messages(merged.get("messages"), "feature_engineering_agent")
        append_agent_feedback(
            merged,
            agent_name="feature_engineering_agent",
            summary_data=response.get("data_engineered"),
            last_human=deps._get_last_human_text(before_msgs),
            format_result_with_llm=deps.format_result_with_llm,
            extra_text="Feature engineering completed.",
            error_text=response.get("feature_engineer_error"),
            error_log_path=response.get("feature_engineer_error_log_path"),
            error_prefix="Feature engineering error",
        )
        feature_data = response.get("data_engineered")
        if feature_data is not None:
            try:
                datasets, active_dataset_id, _did = register_python_transform_dataset(
                    state_with_datasets=state_with_datasets,  # type: ignore[arg-type]
                    data=feature_data,
                    stage="feature",
                    label="feature_data",
                    created_by="Feature_Engineering_Agent",
                    user_request=last_human,
                    function_code=response.get("feature_engineer_function"),
                    function_name=response.get("feature_engineer_function_name"),
                    function_path=response.get("feature_engineer_function_path"),
                    recommended_steps=response.get("recommended_steps"),
                    parent_id=active_dataset_id,
                    error_text=response.get("feature_engineer_error"),
                    error_log_path=response.get("feature_engineer_error_log_path"),
                    summary=response.get("feature_engineering_summary"),
                )
            except Exception:
                pass
        downstream_resets = (
            {
                "eda_artifacts": None,
                "viz_graph": None,
                "model_info": None,
                "mlflow_artifacts": None,
            }
            if feature_data is not None
            else {}
        )
        return {
            **merged,
            "feature_data": feature_data,
            "active_data_key": "feature_data"
            if feature_data is not None
            else state.get("active_data_key"),
            "datasets": datasets,
            "active_dataset_id": active_dataset_id,
            "artifacts": {
                **state.get("artifacts", {}),
                "feature_engineering": response,
                "feature_engineering_details": {
                    "feature_engineer_function": response.get("feature_engineer_function"),
                    "feature_engineer_function_path": response.get(
                        "feature_engineer_function_path"
                    ),
                    "feature_engineer_function_name": response.get(
                        "feature_engineer_function_name"
                    ),
                    "feature_engineer_error": response.get("feature_engineer_error"),
                    "feature_engineer_error_log_path": response.get(
                        "feature_engineer_error_log_path"
                    ),
                    "feature_engineering_summary": response.get("feature_engineering_summary"),
                    "recommended_steps": response.get("recommended_steps"),
                },
            },
            "last_worker": "Feature_Engineering_Agent",
            **downstream_resets,
        }

    return node_fe


__all__ = ["FeNodeDeps", "make_node_fe"]
