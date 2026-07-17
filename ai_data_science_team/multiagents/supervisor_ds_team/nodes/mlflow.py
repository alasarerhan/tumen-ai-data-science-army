from __future__ import annotations

"""Auto-generated mlflow node module.

Extracted from the 3,400-line ``supervisor_ds_team.py`` monolith
during the L2 code-review remediation pass.  Uses dependency
injection via the ``MlflowNodeDeps`` dataclass.
"""

import logging  # noqa: E402, F401
from dataclasses import dataclass  # noqa: E402, F401
from typing import Any, Callable  # noqa: E402, F401

from langchain_core.messages import AIMessage  # noqa: E402, F401

from ai_data_science_team.multiagents.supervisor import (  # noqa: E402, F401
    SupervisorDSState)

logger = logging.getLogger(__name__)


@dataclass
class MlflowNodeDeps:
    """Dependencies for the mlflow node."""
    mlflow_tools_agent: Any
    ensure_df: Any  # was _ensure_df
    format_result_with_llm: Any  # was _format_result_with_llm
    get_active_data: Any  # was _get_active_data
    _get_last_human_text: Any  # was _get_last_human
    is_empty_df: Any  # was _is_empty_df
    merge_messages: Any  # was _merge_messages
    tag_messages: Any  # was _tag_messages
    llm: Any


def make_node_mlflow(deps: MlflowNodeDeps) -> Callable[[SupervisorDSState], dict]:
    """Build the ``node_mlflow`` state-graph node."""

    def node_mlflow(state: SupervisorDSState):
        logger.info("---MLFLOW TOOLS---")
        before_msgs = list(state.get("messages", []) or [])
        deps.mlflow_tools_agent.invoke_messages(
            messages=before_msgs)
        response = deps.mlflow_tools_agent.response or {}
        merged = deps.merge_messages(before_msgs, response)
        merged["messages"] = deps.tag_messages(merged.get("messages"), "mlflow_tools_agent")
        summary_text = deps.format_result_with_llm(
            "mlflow_tools_agent",
            response.get("mlflow_artifacts"),
            deps._get_last_human_text(before_msgs),
            extra_text="MLflow artifacts.")
        if summary_text:
            merged["messages"].append(
                AIMessage(content=summary_text, name="mlflow_tools_agent")
            )
        mlflow_artifacts = response.get("mlflow_artifacts")
        return {
            **merged,
            "mlflow_artifacts": mlflow_artifacts,
            "artifacts": {
                **state.get("artifacts", {}),
                "mlflow": mlflow_artifacts,
            },
            "last_worker": "MLflow_Tools_Agent",
        }


    return node_mlflow



__all__ = ["MlflowNodeDeps", "make_node_mlflow"]
