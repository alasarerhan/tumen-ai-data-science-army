"""Auto-generated eval node module.

Extracted from the 3,400-line ``supervisor_ds_team.py`` monolith
during the L2 code-review remediation pass.  Uses dependency
injection via the ``EvalNodeDeps`` dataclass.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from langchain_core.messages import AIMessage

from ai_data_science_team.multiagents.supervisor import (
    SupervisorDSState,
    ensure_df,
    get_active_data,
    is_empty_df,
    merge_messages,
    tag_messages,
)

logger = logging.getLogger(__name__)


@dataclass
class EvalNodeDeps:
    """Dependencies for the eval node."""
    model_evaluation_agent: Any
    ensure_df: Any  # was _ensure_df
    get_active_data: Any  # was _get_active_data
    is_empty_df: Any  # was _is_empty_df
    merge_messages: Any  # was _merge_messages
    tag_messages: Any  # was _tag_messages


def make_node_eval(deps: EvalNodeDeps) -> Callable[[SupervisorDSState], dict]:
    """Build the ``node_eval`` state-graph node."""

    def node_eval(state: SupervisorDSState):
        logger.info("---MODEL EVALUATION---")
        before_msgs = list(state.get("messages", []) or [])
        feature_df = deps.ensure_df(state.get("feature_data"))
        active_df = (
            feature_df
            if not deps.is_empty_df(feature_df)
            else deps.ensure_df(
                deps.get_active_data(
                    state, ["data_cleaned", "data_wrangled", "data_sql", "data_raw"]
                )
            )
        )
        if deps.is_empty_df(active_df):
            return {
                "messages": [
                    AIMessage(
                        content="No dataset is available for evaluation. Load data and train a model first.",
                        name="model_evaluation_agent",
                    )
                ],
                "last_worker": "Model_Evaluation_Agent",
            }
        h2o_art = (state.get("artifacts") or {}).get("h2o")
        model_artifacts = h2o_art if isinstance(h2o_art, dict) else {}
        deps.model_evaluation_agent.invoke_messages(
            messages=before_msgs,
            data_raw=active_df,
            model_artifacts=model_artifacts,
            target_variable=state.get("target_variable"),
        )
        response = deps.model_evaluation_agent.response or {}
        merged = deps.merge_messages(before_msgs, response)
        merged["messages"] = deps.tag_messages(
            merged.get("messages"), "model_evaluation_agent"
        )
        eval_artifacts = response.get("eval_artifacts")
        plotly_graph = response.get("plotly_graph")
        if isinstance(eval_artifacts, dict) and eval_artifacts.get("error"):
            merged["messages"].append(
                AIMessage(
                    content="Model evaluation error:\n" + str(eval_artifacts.get("error")),
                    name="model_evaluation_agent",
                )
            )
        return {
            **merged,
            "eval_artifacts": eval_artifacts,
            "artifacts": {
                **state.get("artifacts", {}),
                "eval": {
                    "eval_artifacts": eval_artifacts,
                    "plotly_graph": plotly_graph,
                },
            },
            "last_worker": "Model_Evaluation_Agent",
        }


    return node_eval



__all__ = ["EvalNodeDeps", "make_node_eval"]
