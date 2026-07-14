"""Auto-generated viz node module.

Extracted from the 3,400-line ``supervisor_ds_team.py`` monolith
during the L2 code-review remediation pass.  Uses dependency
injection via the ``VizNodeDeps`` dataclass.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from langchain_core.messages import AIMessage

from ai_data_science_team.multiagents.supervisor import (
    SupervisorDSState,
    _get_last_human_text,
    ensure_df,
    get_active_data,
    is_empty_df,
    merge_messages,
    tag_messages,
)

logger = logging.getLogger(__name__)


@dataclass
class VizNodeDeps:
    """Dependencies for the viz node."""
    data_visualization_agent: Any
    ensure_df: Any  # was _ensure_df
    get_active_data: Any  # was _get_active_data
    _get_last_human_text: Any  # was _get_last_human
    is_empty_df: Any  # was _is_empty_df
    merge_messages: Any  # was _merge_messages
    tag_messages: Any  # was _tag_messages


def make_node_viz(deps: VizNodeDeps) -> Callable[[SupervisorDSState], dict]:
    """Build the ``node_viz`` state-graph node."""

    def node_viz(state: SupervisorDSState):
        logger.info("---DATA VISUALIZATION---")
        before_msgs = list(state.get("messages", []) or [])
        last_human = deps._get_last_human_text(before_msgs)
        active_df = deps.ensure_df(
            deps.get_active_data(
                state,
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
                        content="No dataset is available to plot. Load a file (or run a SQL query) first.",
                        name="data_visualization_agent",
                    )
                ],
                "last_worker": "Data_Visualization_Agent",
            }
        deps.data_visualization_agent.invoke_messages(
            messages=before_msgs,
            user_instructions=last_human,
            data_raw=active_df,
        )
        response = deps.data_visualization_agent.response or {}
        merged = deps.merge_messages(before_msgs, response)
        merged["messages"] = deps.tag_messages(
            merged.get("messages"), "data_visualization_agent"
        )
        plotly_graph = response.get("plotly_graph")
        viz_error = response.get("data_visualization_error")
        viz_error_path = response.get("data_visualization_error_log_path")
        viz_warning = response.get("data_visualization_warning")
        try:
            from ai_data_science_team.utils.plotly import plotly_from_dict

            fig = plotly_from_dict(plotly_graph) if plotly_graph else None
            trace_types = (
                sorted(
                    {
                        getattr(t, "type", None)
                        for t in getattr(fig, "data", [])
                        if getattr(t, "type", None)
                    }
                )
                if fig is not None
                else []
            )
            title = None
            if fig is not None:
                try:
                    title = getattr(getattr(fig.layout, "title", None), "text", None)
                except Exception:
                    title = None
            viz_summary = (
                response.get("data_visualization_summary") or "Visualization generated."
            )
            if trace_types:
                viz_summary = f"{viz_summary} Trace types: {', '.join(trace_types)}."
            if title:
                viz_summary = f"{viz_summary} Title: {title}."
            merged["messages"].append(
                AIMessage(content=viz_summary, name="data_visualization_agent")
            )
        except Exception:
            pass
        if isinstance(viz_error, str) and viz_error:
            err_bits = [viz_error]
            if isinstance(viz_error_path, str) and viz_error_path:
                err_bits.append(f"Log: {viz_error_path}")
            merged["messages"].append(
                AIMessage(
                    content="Visualization error:\n" + "\n".join(err_bits),
                    name="data_visualization_agent",
                )
            )
        if isinstance(viz_warning, str) and viz_warning:
            merged["messages"].append(
                AIMessage(
                    content="Visualization warning:\n" + viz_warning,
                    name="data_visualization_agent",
                )
            )
        return {
            **merged,
            "viz_graph": plotly_graph,
            "artifacts": {
                **state.get("artifacts", {}),
                "viz": {
                    "plotly_graph": plotly_graph,
                    "data_visualization_function": response.get(
                        "data_visualization_function"
                    ),
                    "error": viz_error,
                    "error_log_path": viz_error_path,
                    "warning": viz_warning,
                },
            },
            "last_worker": "Data_Visualization_Agent",
        }


    return node_viz



__all__ = ["VizNodeDeps", "make_node_viz"]
