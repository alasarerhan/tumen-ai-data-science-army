from __future__ import annotations


import json
from typing import Any, Optional

from langchain_core.prompts import ChatPromptTemplate


def format_listing_with_llm(llm: Any, rows: list, last_human: str):
    """Render a short directory-listing summary and markdown table."""
    if not rows:
        return None

    limited = rows[:30]
    try:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are formatting a directory listing for the user. "
                    "Return a concise markdown summary and a markdown table with columns "
                    "`filename`, `type`, and `path` (omit missing columns). "
                    "Do not add extra narration beyond the summary.",
                ),
                (
                    "human",
                    "User request: {last_human}\n\n"
                    "Rows (JSON list): {rows_json}\n\n"
                    "Return:\n"
                    "1) One-sentence summary.\n"
                    "2) A markdown table.",
                ),
            ]
        )
        rows_json = json.dumps(limited)
        response = (prompt | llm).invoke(
            {"last_human": last_human, "rows_json": rows_json}
        )
        return getattr(response, "content", None) or str(response)
    except Exception:
        return None


def format_dataset_with_llm(
    llm: Any,
    df_dict: dict,
    last_human: str,
    max_rows: int = 10,
    max_cols: int = 6,
):
    """Summarize a dataset and render a markdown preview table."""
    if not df_dict:
        return None

    try:
        import pandas as pd  # noqa: E402, F401

        df = pd.DataFrame(df_dict)
        table_md = df.iloc[:max_rows, :max_cols].to_markdown(index=False)
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are summarizing a dataset for the user. "
                    "Return a concise summary and a small markdown table preview already provided. "
                    "Do not add extra narration beyond the summary and the table.",
                ),
                (
                    "human",
                    "User request: {last_human}\n\n"
                    "Preview table (markdown):\n{table_md}\n\n"
                    "Dataset shape: {shape}",
                ),
            ]
        )
        response = (prompt | llm).invoke(
            {
                "last_human": last_human,
                "table_md": table_md,
                "shape": str(df.shape),
            }
        )
        return getattr(response, "content", None) or str(response)
    except Exception:
        return None


def format_result_with_llm(
    llm: Any,
    agent_name: str,
    df_dict: Optional[dict],
    last_human: str,
    extra_text: str = "",
    max_rows: int = 6,
    max_cols: int = 6,
):
    """Summarize an agent result and include a markdown table preview when available."""
    try:
        preview_md = ""
        shape = "unknown"
        if df_dict:
            import pandas as pd  # noqa: E402, F401

            df = pd.DataFrame(df_dict)
            preview_md = df.iloc[:max_rows, :max_cols].to_markdown(index=False)
            shape = str(df.shape)

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    f"You are summarizing the output of the {agent_name}. "
                    "Return a concise summary and, if provided, include the markdown table preview as-is. "
                    "Do not add extra narration beyond the summary and table.",
                ),
                (
                    "human",
                    "User request: {last_human}\n\n"
                    "Extra context: {extra_text}\n\n"
                    "Preview table (markdown):\n{preview_md}\n\n"
                    "Data shape: {shape}",
                ),
            ]
        )
        response = (prompt | llm).invoke(
            {
                "last_human": last_human,
                "extra_text": extra_text or "None",
                "preview_md": preview_md or "None",
                "shape": shape,
            }
        )
        return getattr(response, "content", None) or str(response)
    except Exception:
        return None
