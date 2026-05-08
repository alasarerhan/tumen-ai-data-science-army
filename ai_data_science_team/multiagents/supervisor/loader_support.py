from __future__ import annotations

import re
from typing import Any


def normalize_loader_artifacts(loader_artifacts: Any) -> dict[str, Any]:
    if loader_artifacts is None:
        return {}
    if isinstance(loader_artifacts, dict):
        if {"status", "data"}.issubset(set(loader_artifacts.keys())):
            return {"load_file": loader_artifacts}
        return loader_artifacts
    return {"artifact": loader_artifacts}


def extract_loader_artifact_results(
    artifacts_map: dict[str, Any],
) -> tuple[
    Any,
    Any,
    str | None,
    list[str] | None,
    list[tuple[str, Any]] | None,
    list[tuple[str, Any]],
]:
    dir_listing = None
    loaded_dataset = None
    loaded_dataset_label = None
    multiple_loaded_files: list[str] | None = None
    multiple_loaded_datasets: list[tuple[str, Any]] | None = None
    load_file_ok_items: list[tuple[str, Any]] = []

    for key, value in artifacts_map.items():
        if str(key).startswith("list_directory") or str(key).startswith(
            "search_files_by_pattern"
        ):
            dir_listing = value
            break

    for key, value in artifacts_map.items():
        tool_name = str(key)
        if tool_name.startswith("load_file") and isinstance(value, dict):
            if value.get("status") == "ok" and value.get("data") is not None:
                load_file_ok_items.append((tool_name, value.get("data")))
            continue

        if tool_name.startswith("load_directory") and isinstance(value, dict):
            ok_items = []
            for filename, info in value.items():
                if (
                    isinstance(info, dict)
                    and info.get("status") == "ok"
                    and info.get("data") is not None
                ):
                    ok_items.append((filename, info.get("data")))
            if len(ok_items) == 1 and loaded_dataset is None:
                loaded_dataset_label, loaded_dataset = ok_items[0]
                continue
            if len(ok_items) > 1:
                multiple_loaded_files = [filename for filename, _ in ok_items]
                multiple_loaded_datasets = ok_items
                loaded_dataset = None
                loaded_dataset_label = None
                break

    return (
        dir_listing,
        loaded_dataset,
        loaded_dataset_label,
        multiple_loaded_files,
        multiple_loaded_datasets,
        load_file_ok_items,
    )


def infer_requested_load_labels(
    last_human: str,
    load_file_ok_items: list[tuple[str, Any]],
) -> list[str]:
    requested = re.findall(
        r"(?:`|\"|')?([^\s'\"`]+\.(?:csv|tsv|parquet|xlsx?|jsonl|ndjson|json)(?:\.gz)?)",
        last_human or "",
        flags=re.IGNORECASE,
    )
    requested = [item.strip() for item in requested if str(item).strip()]
    seen_requested: set[str] = set()
    labels: list[str] = []
    for item in requested:
        if item in seen_requested:
            continue
        seen_requested.add(item)
        labels.append(item)

    if len(labels) != len(load_file_ok_items):
        labels = [name for name, _ in load_file_ok_items]

    return labels


def collect_loader_errors(loader_artifacts: Any) -> list[str]:
    errors: list[str] = []
    if not loader_artifacts or not isinstance(loader_artifacts, dict):
        return errors

    for key, value in loader_artifacts.items():
        if isinstance(value, dict):
            if value.get("status") == "error" and value.get("error"):
                errors.append(f"{key}: {value.get('error')}")
            for filename, info in value.items():
                if (
                    isinstance(info, dict)
                    and info.get("status") == "error"
                    and info.get("error")
                ):
                    errors.append(f"{filename}: {info.get('error')}")
    return errors
