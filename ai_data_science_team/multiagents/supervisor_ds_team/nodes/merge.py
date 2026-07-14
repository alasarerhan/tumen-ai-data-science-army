"""Auto-generated merge node module.

Extracted from the 3,400-line ``supervisor_ds_team.py`` monolith
during the L2 code-review remediation pass.  Uses dependency
injection via the ``MergeNodeDeps`` dataclass.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from langchain_core.messages import AIMessage

from ai_data_science_team.multiagents.supervisor import (
    SupervisorDSState,
    _get_last_human_text,
    ensure_dataset_registry,
    ensure_df,
    is_empty_df,
    register_dataset,
    sha256_text,
    tag_messages,
    truncate_text,
)

logger = logging.getLogger(__name__)


@dataclass
class MergeNodeDeps:
    """Dependencies for the merge node."""
    ensure_dataset_registry: Any  # was _ensure_dataset_registry
    ensure_df: Any  # was _ensure_df
    _get_last_human_text: Any  # was _get_last_human
    is_empty_df: Any  # was _is_empty_df
    register_dataset: Any  # was _register_dataset
    sha256_text: Any  # was _sha256_text
    tag_messages: Any  # was _tag_messages
    truncate_text: Any  # was _truncate_text


def make_node_merge(deps: MergeNodeDeps) -> Callable[[SupervisorDSState], dict]:
    """Build the ``node_merge`` state-graph node."""

    def node_merge(state: SupervisorDSState):
        logger.info("---DATA MERGE---")
        before_msgs = list(state.get("messages", []) or [])
        last_human = deps._get_last_human_text(before_msgs)
        datasets, active_dataset_id = deps.ensure_dataset_registry(state)
        state_with_datasets = {  # type: ignore[typeddict-item]
            **{k: v for k, v in (state or {}).items()},  # type: ignore[typeddict-item]
            "datasets": datasets,
            "active_dataset_id": active_dataset_id,
        }

        cfg = (state.get("artifacts") or {}).get("config") or {}
        merge_cfg = cfg.get("merge") if isinstance(cfg, dict) else None
        merge_cfg = merge_cfg if isinstance(merge_cfg, dict) else {}
        selected_ids = resolve_selected_dataset_ids(
            datasets,
            active_dataset_id,
            merge_cfg,
            last_human,
        )

        if len(selected_ids) < 2:
            available = available_datasets_lines(datasets)
            msg = (
                "To merge datasets, mention 2+ dataset IDs in your request (or use Pipeline Studio to create a merge node).\n\n"
                + ("Available datasets:\n" + "\n".join(available) if available else "")
            ).strip()
            return {
                "messages": [AIMessage(content=msg, name="data_merge_agent")],
                "last_worker": "Data_Merge_Agent",
            }

        dfs = []
        for did in selected_ids:
            entry = datasets.get(did)
            df = deps.ensure_df(entry.get("data") if isinstance(entry, dict) else None)
            if deps.is_empty_df(df):
                return {
                    "messages": [
                        AIMessage(
                            content=f"Dataset `{did}` is empty/unavailable; load it again before merging.",
                            name="data_merge_agent",
                        )
                    ],
                    "last_worker": "Data_Merge_Agent",
                }
            dfs.append(df)

        merge_plan = execute_merge_plan(dfs, merge_cfg, last_human)
        if not merge_plan.get("ok"):
            return {
                "messages": [
                    AIMessage(
                        content=str(merge_plan.get("error_message") or "Merge failed."),
                        name="data_merge_agent",
                    )
                ],
                "last_worker": "Data_Merge_Agent",
            }

        op = str(merge_plan.get("operation") or "join")
        merged_df = merge_plan["merged_df"]
        merge_meta: dict[str, Any] = {
            "dataset_ids": selected_ids,
            **dict(merge_plan.get("merge_meta") or {}),
        }
        merge_code = str(merge_plan.get("merge_code") or "")
        merge_code_hash = deps.sha256_text(merge_code)

        merged_data = merged_df
        try:
            import pandas as pd

            if isinstance(merged_df, pd.DataFrame):
                merged_data = merged_df.to_dict()
        except Exception:
            merged_data = merged_df

        datasets, active_dataset_id, merged_id = deps.register_dataset(
            state_with_datasets,  # type: ignore[arg-type]
            data=merged_data,
            stage="wrangled",
            label="data_merged",
            created_by="Data_Merge_Agent",
            provenance={
                "source_type": "agent",
                "user_request": last_human,
                "transform": {
                    "kind": "python_merge",
                    "merge": merge_meta,
                    "merge_code": deps.truncate_text(merge_code, 12000),
                    "code_sha256": merge_code_hash,
                },
            },
            parent_ids=selected_ids,
            make_active=True,
        )

        msg_lines = [
            f"Merged {len(selected_ids)} datasets ({op}).",
            f"Result shape: {getattr(merged_df, 'shape', None)}.",
            f"Active dataset id: `{merged_id}`.",
        ]
        merged = {
            "messages": [
                AIMessage(
                    content=" ".join([m for m in msg_lines if m]),
                    name="data_merge_agent",
                )
            ]
        }
        merged["messages"] = deps.tag_messages(merged.get("messages"), "data_merge_agent")
        downstream_resets = {
            "data_cleaned": None,
            "eda_artifacts": None,
            "viz_graph": None,
            "feature_data": None,
            "model_info": None,
            "mlflow_artifacts": None,
        }
        return {
            **merged,
            "data_wrangled": merged_data,
            "active_data_key": "data_wrangled",
            "datasets": datasets,
            "active_dataset_id": active_dataset_id,
            "artifacts": {
                **state.get("artifacts", {}),
                "merge": {
                    "dataset_ids": selected_ids,
                    "operation": op,
                    "active_dataset_id": merged_id,
                    "merge_config": merge_cfg,
                },
            },
            "last_worker": "Data_Merge_Agent",
            **downstream_resets,
        }


    return node_merge



__all__ = ["MergeNodeDeps", "make_node_merge"]
