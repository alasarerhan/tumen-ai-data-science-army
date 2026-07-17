from __future__ import annotations

"""Auto-generated eda node module.

Extracted from the 3,400-line ``supervisor_ds_team.py`` monolith
during the L2 code-review remediation pass.  Uses dependency
injection via the ``EdaNodeDeps`` dataclass.
"""

import logging  # noqa: E402, F401
from dataclasses import dataclass  # noqa: E402, F401
from typing import Any, Callable  # noqa: E402, F401

from langchain_core.messages import AIMessage  # noqa: E402, F401

from ai_data_science_team.multiagents.supervisor import (  # noqa: E402, F401
    SupervisorDSState)

logger = logging.getLogger(__name__)


@dataclass
class EdaNodeDeps:
    """Dependencies for the eda node."""
    eda_tools_agent: Any
    ensure_df: Any  # was _ensure_df
    format_result_with_llm: Any  # was _format_result_with_llm
    get_active_data: Any  # was _get_active_data
    _get_last_human_text: Any  # was _get_last_human
    is_empty_df: Any  # was _is_empty_df
    merge_messages: Any  # was _merge_messages
    tag_messages: Any  # was _tag_messages
    llm: Any


def make_node_eda(deps: EdaNodeDeps) -> Callable[[SupervisorDSState], dict]:
    """Build the ``node_eda`` state-graph node."""

    def node_eda(state: SupervisorDSState):
        logger.info("---EDA TOOLS---")
        before_msgs = list(state.get("messages", []) or [])
        last_human = deps._get_last_human_text(before_msgs).lower()
        feature_df = deps.ensure_df(state.get("feature_data"))
        wants_feature_engineered_report = (
            ("feature-engineered" in last_human or "feature engineered" in last_human)
            and (
                "data" in last_human
                or "dataset" in last_human
                or "features" in last_human
            )
        ) or ("engineered features" in last_human)
        active_df = deps.ensure_df(
            deps.get_active_data(
                state,
                [
                    "data_cleaned",
                    "data_wrangled",
                    "data_sql",
                    "data_raw",
                    "feature_data",
                ])
        )
        # If the user explicitly references feature-engineered data, prefer it for EDA/reporting.
        if wants_feature_engineered_report and not deps.is_empty_df(feature_df):
            active_df = feature_df
        if deps.is_empty_df(active_df):
            return {
                "messages": [
                    AIMessage(
                        content="No dataset is available for EDA. Load a file (or run a SQL query) first.",
                        name="eda_tools_agent")
                ],
                "last_worker": "EDA_Tools_Agent",
            }
        deps.eda_tools_agent.invoke_messages(
            messages=before_msgs,
            data_raw=active_df)
        response = deps.eda_tools_agent.response or {}
        merged = deps.merge_messages(before_msgs, response)
        merged["messages"] = deps.tag_messages(merged.get("messages"), "eda_tools_agent")
        logger.info(
            f"  eda artifacts keys={response.get('eda_artifacts') and list(response.get('eda_artifacts').keys()) if isinstance(response.get('eda_artifacts'), dict) else None}"
        )
        summary_text = deps.format_result_with_llm(
            "eda_tools_agent",
            response.get("eda_artifacts", {}).get("describe_dataset")
            if isinstance(response.get("eda_artifacts"), dict)
            else None,
            deps._get_last_human_text(before_msgs),
            extra_text="EDA summary.")
        if summary_text:
            merged["messages"].append(
                AIMessage(content=summary_text, name="eda_tools_agent")
            )
        eda_artifacts = response.get("eda_artifacts")
        return {
            **merged,
            "eda_artifacts": eda_artifacts,
            "artifacts": {
                **state.get("artifacts", {}),
                "eda": eda_artifacts,
            },
            "last_worker": "EDA_Tools_Agent",
        }


    return node_eda



__all__ = ["EdaNodeDeps", "make_node_eda"]
