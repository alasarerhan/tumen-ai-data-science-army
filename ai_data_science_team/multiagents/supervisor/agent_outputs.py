from __future__ import annotations


from collections.abc import Callable, Mapping
from typing import Any

from langchain_core.messages import AIMessage

from .datasets import register_dataset, sha256_text, truncate_text
from .messages import append_error_message


def append_agent_feedback(
    merged: dict[str, Any],
    *,
    agent_name: str,
    summary_data: Any,
    last_human: str,
    format_result_with_llm: Callable[[str, Any, str, str], str | None],
    extra_text: str,
    error_text: str | None,
    error_log_path: str | None,
    error_prefix: str,
):
    summary_text = format_result_with_llm(
        agent_name,
        summary_data,
        last_human,
        extra_text,
    )
    if summary_text:
        merged["messages"].append(AIMessage(content=summary_text, name=agent_name))
    append_error_message(
        merged,
        agent_name,
        error_text,
        error_log_path,
        prefix=error_prefix,
    )


def register_python_transform_dataset(
    *,
    state_with_datasets: Mapping[str, Any],
    data: Any,
    stage: str,
    label: str,
    created_by: str,
    user_request: str,
    function_code: str | None,
    function_name: str | None,
    function_path: str | None,
    recommended_steps: Any,
    parent_id: str | None,
    error_text: str | None,
    error_log_path: str | None,
    summary: Any = None,
):
    code_hash = sha256_text(function_code)
    transform: dict[str, Any] = {
        "kind": "python_function",
        "function_name": function_name,
        "function_path": function_path,
        "function_code": truncate_text(function_code, 12000),
        "code_sha256": code_hash,
        "recommended_steps": recommended_steps,
        "error": error_text,
        "error_log_path": error_log_path,
    }
    if summary is not None:
        transform["summary"] = summary

    return register_dataset(
        state_with_datasets,
        data=data,
        stage=stage,
        label=label,
        created_by=created_by,
        provenance={
            "source_type": "agent",
            "user_request": user_request,
            "transform": transform,
        },
        parent_id=parent_id,
        make_active=True,
    )
