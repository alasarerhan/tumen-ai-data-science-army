from __future__ import annotations

import os
from typing import Any, Callable, Optional

from langchain_core.messages import AIMessage


def summarize_multi_loaded_datasets(
    multiple_loaded_datasets: list[tuple[str, Any]],
    loaded_dataset_label: str | None,
    data_raw: Any,
) -> AIMessage:
    try:
        import pandas as pd

        lines = []
        for filename, data in multiple_loaded_datasets:
            label = os.path.basename(str(filename)) or str(filename)
            shape_txt = ""
            try:
                df = pd.DataFrame(data)
                shape_txt = f" ({df.shape[0]} rows x {df.shape[1]} cols)"
            except Exception:
                pass
            lines.append(f"- {label}{shape_txt}")

        active_label = os.path.basename(str(loaded_dataset_label)) or str(
            loaded_dataset_label or ""
        )
        preview_txt = ""
        try:
            df_active = pd.DataFrame(data_raw) if isinstance(data_raw, dict) else None
            if df_active is not None:
                preview_df = df_active.head(5)
                max_cols = 10
                if preview_df.shape[1] > max_cols:
                    preview_df = preview_df.iloc[:, :max_cols]
                preview_txt = (
                    "\n\nPreview (first 5 rows):\n\n"
                    + preview_df.to_markdown(index=False)
                )
        except Exception:
            pass

        content = (
            f"Loaded {len(multiple_loaded_datasets)} datasets:\n\n"
            + "\n".join(lines)
            + (f"\n\nActive dataset: {active_label}." if active_label else "")
            + preview_txt
            + "\n\nUse the sidebar dataset selector to switch the active dataset, or use Pipeline Studio to merge them."
        )
    except Exception:
        content = (
            f"Loaded {len(multiple_loaded_datasets)} datasets. "
            "Use the sidebar dataset selector to switch the active dataset, or use Pipeline Studio to merge them."
        )
    return AIMessage(content=content, name="data_loader_agent")


def summarize_multiple_loaded_files(multiple_loaded_files: list[str]) -> AIMessage:
    joined = ", ".join(multiple_loaded_files[:20])
    more = (
        f" (+{len(multiple_loaded_files) - 20} more)"
        if len(multiple_loaded_files) > 20
        else ""
    )
    return AIMessage(
        content=(
            "Loaded multiple datasets from the directory:\n\n"
            f"{joined}{more}\n\n"
            "Tell me which file you want to load (e.g., `load <filename>`)."
        ),
        name="data_loader_agent",
    )


def _rows_from_dir_listing(dir_listing: Any) -> tuple[list[str], list[dict[str, Any]]]:
    names: list[str] = []
    rows: list[dict[str, Any]] = []
    if isinstance(dir_listing, list):
        iterable = dir_listing
    elif isinstance(dir_listing, dict):
        iterable = dir_listing.values()
    else:
        iterable = []

    for item in iterable:
        if isinstance(item, dict):
            if "filename" in item:
                names.append(str(item.get("filename")))
                rows.append(
                    {
                        "filename": item.get("filename"),
                        "type": item.get("type"),
                        "path": item.get("path") or item.get("filepath"),
                    }
                )
                continue
            if "file_path" in item:
                fp = item.get("file_path")
                filename = os.path.basename(fp) if isinstance(fp, str) else str(fp)
                names.append(filename)
                rows.append({"filename": filename, "type": "file", "path": fp})
                continue
            if "absolute_path" in item or "name" in item:
                absolute_path = item.get("absolute_path")
                filename = item.get("name") or (
                    os.path.basename(absolute_path)
                    if isinstance(absolute_path, str)
                    else str(absolute_path)
                )
                names.append(str(filename))
                rows.append(
                    {
                        "filename": filename,
                        "type": item.get("type"),
                        "path": absolute_path,
                    }
                )
                continue

        names.append(str(item))
        rows.append({"filename": str(item)})

    return names, rows


def summarize_directory_listing(
    dir_listing: Any,
    last_human: str,
    format_listing_with_llm: Callable[[list[dict[str, Any]], str], Optional[str]],
) -> tuple[AIMessage, Any]:
    try:
        names, rows = _rows_from_dir_listing(dir_listing)
        wants_csv_only = "csv" in last_human and ("list" in last_human or "files" in last_human)
        if wants_csv_only and rows:
            rows = [
                row
                for row in rows
                if str(row.get("filename", "")).lower().endswith(".csv")
            ]
            names = [row.get("filename") for row in rows if row.get("filename")]
            if not rows:
                return AIMessage(
                    content="No CSV files found in that directory.",
                    name="data_loader_agent",
                ), None

        msg_text = "Found files: " + ", ".join(names) if names else "Found directory contents."
        table_text = ""
        if rows:
            import pandas as pd

            df_listing = pd.DataFrame(rows)
            table_cols = [
                column
                for column in ["filename", "type", "path"]
                if column in df_listing.columns
            ]
            table_text = df_listing[table_cols].to_markdown(index=False)

        llm_text = format_listing_with_llm(rows, last_human) if rows else None
        if llm_text:
            return AIMessage(content=llm_text, name="data_loader_agent"), dir_listing
        if table_text:
            return (
                AIMessage(content=f"{msg_text}\n\n{table_text}", name="data_loader_agent"),
                dir_listing,
            )
        return AIMessage(content=msg_text, name="data_loader_agent"), dir_listing
    except Exception:
        return AIMessage(
            content="Listed directory contents.",
            name="data_loader_agent",
        ), dir_listing


def summarize_loaded_dataset(
    data_raw: dict[str, Any],
    last_human: str,
    format_result_with_llm: Callable[[str, Optional[dict], str], Optional[str]],
) -> AIMessage:
    try:
        import pandas as pd

        df = pd.DataFrame(data_raw)
        wants_preview_rows = any(
            key in last_human
            for key in (
                "head",
                "preview",
                "first 5",
                "first five",
                "first 5 rows",
                "first five rows",
                "show the first",
                "show first",
                "show rows",
            )
        )

        max_cols = 10
        preview_df = df.head(5)
        col_note = ""
        if preview_df.shape[1] > max_cols:
            preview_df = preview_df.iloc[:, :max_cols]
            col_note = f" (showing first {max_cols} of {df.shape[1]} columns)"
        table_md = preview_df.to_markdown(index=False)

        if wants_preview_rows:
            content = f"Loaded dataset with shape {df.shape}.{col_note}\n\n{table_md}"
        else:
            llm_text = format_result_with_llm("data_loader_agent", data_raw, last_human)
            content = llm_text or f"Loaded dataset with shape {df.shape}.{col_note}\n\n{table_md}"
        return AIMessage(content=content, name="data_loader_agent")
    except Exception:
        return AIMessage(
            content="Loaded dataset successfully. What would you like to do next?",
            name="data_loader_agent",
        )


def summarize_loader_failure(loader_artifacts: Any) -> AIMessage:
    errors: list[str] = []
    try:
        if isinstance(loader_artifacts, dict):
            if {"status", "data"}.issubset(set(loader_artifacts.keys())):
                error_text = loader_artifacts.get("error")
                if isinstance(error_text, str) and error_text.strip():
                    errors.append(error_text.strip())
            else:
                for key, value in loader_artifacts.items():
                    if not str(key).startswith("load_file"):
                        continue
                    if isinstance(value, dict) and value.get("status") != "ok":
                        error_text = value.get("error")
                        if isinstance(error_text, str) and error_text.strip():
                            errors.append(error_text.strip())
    except Exception:
        errors = []

    errors_txt = ""
    if errors:
        unique_errors: list[str] = []
        seen: set[str] = set()
        for error_text in errors:
            if error_text in seen:
                continue
            seen.add(error_text)
            unique_errors.append(error_text)
        shown = unique_errors[:3]
        errors_txt = "\n\nErrors:\n" + "\n".join([f"- {error}" for error in shown])
        if len(unique_errors) > 3:
            errors_txt += f"\n- (+{len(unique_errors) - 3} more)"

    return AIMessage(
        content=(
            "I couldn't load a tabular dataset from that request. "
            f"{errors_txt}\n\n"
            "Try specifying a concrete file path (e.g., `data/churn_data.csv`) "
            "or ask me to list files in a directory first."
        ),
        name="data_loader_agent",
    )
