from __future__ import annotations

import re
import time

import pandas as pd

from ai_data_science_team.utils.sandbox import run_code_sandboxed_subprocess


def _dataset_entry_to_df(entry: dict) -> pd.DataFrame | None:
    if not isinstance(entry, dict):
        return None
    data = entry.get("data")
    try:
        if isinstance(data, pd.DataFrame):
            return data
    except Exception:
        pass
    try:
        if isinstance(data, dict):
            return pd.DataFrame.from_dict(data)
        if isinstance(data, list):
            return pd.DataFrame(data)
    except Exception:
        return None
    return None


def _infer_first_def_name(code: str) -> str | None:
    if not isinstance(code, str) or not code:
        return None
    match = re.search(
        r"^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
        code,
        flags=re.MULTILINE,
    )
    return match.group(1) if match else None


def _normalize_pipeline_stage(stage: str) -> str:
    normalized_stage = stage.strip().lower() if isinstance(stage, str) else ""
    normalized_stage = re.sub(r"[^a-z0-9_]+", "_", normalized_stage)
    normalized_stage = re.sub(r"_+", "_", normalized_stage).strip("_")
    return normalized_stage or "custom"


def _exec_python_transform(
    *,
    code: str,
    df_in: pd.DataFrame,
    fn_name_hint: str | None = None,
) -> tuple[pd.DataFrame, str | None]:
    code = code if isinstance(code, str) else ""
    code = code.strip()
    if not code:
        raise ValueError("Draft code is empty; nothing to run.")

    inferred_function_name = _infer_first_def_name(code)
    fn_name_hint = fn_name_hint.strip() if isinstance(fn_name_hint, str) else None
    function_name = fn_name_hint or inferred_function_name or "transform"

    result, error = run_code_sandboxed_subprocess(
        code_snippet=code,
        function_name=function_name,
        data=df_in.to_dict(),
        timeout=60,
        memory_limit_mb=512,
        data_format="dataframe",
    )

    if error:
        raise ValueError(f"Code execution error: {error}")

    output_data = None
    if result is not None:
        try:
            if isinstance(result, dict):
                output_data = pd.DataFrame.from_dict(result)
            elif isinstance(result, list):
                output_data = pd.DataFrame(result)
        except Exception:
            output_data = None

    if not isinstance(output_data, pd.DataFrame):
        raise ValueError("Draft function did not return a pandas DataFrame.")
    return output_data, function_name


def _entry_parent_ids(entry_obj: dict) -> list[str]:
    entry_obj = entry_obj if isinstance(entry_obj, dict) else {}
    parent_ids: list[str] = []
    listed_parent_ids = entry_obj.get("parent_ids")
    if isinstance(listed_parent_ids, list):
        parent_ids.extend([str(parent) for parent in listed_parent_ids if isinstance(parent, str) and parent])
    parent_id = entry_obj.get("parent_id")
    if isinstance(parent_id, str) and parent_id and parent_id not in parent_ids:
        parent_ids.insert(0, parent_id)
    return [parent for parent in parent_ids if parent]


def _build_children_index(datasets: dict) -> dict[str, set[str]]:
    datasets = datasets if isinstance(datasets, dict) else {}
    children_index: dict[str, set[str]] = {}
    for dataset_id, dataset_entry in datasets.items():
        if not isinstance(dataset_id, str) or not dataset_id or not isinstance(dataset_entry, dict):
            continue
        for parent_id in _entry_parent_ids(dataset_entry):
            children_index.setdefault(parent_id, set()).add(dataset_id)
    return children_index


def _descendants(start_id: str, children_index: dict[str, set[str]]) -> set[str]:
    start_id = start_id.strip() if isinstance(start_id, str) else ""
    if not start_id:
        return set()
    seen: set[str] = set()
    stack = list(children_index.get(start_id, set()))
    while stack:
        node_id = stack.pop()
        if node_id in seen:
            continue
        seen.add(node_id)
        stack.extend(list(children_index.get(node_id, set())))
    return seen


def _pipeline_studio_branch_ids_for_datasets(root_id: str, datasets: dict) -> set[str]:
    root_id = root_id.strip() if isinstance(root_id, str) else ""
    if not root_id:
        return set()
    child_index = _build_children_index(datasets)
    return {root_id} | _descendants(root_id, child_index)


def _build_pipeline_semantic_graph(
    *,
    pipeline_hash: str,
    node_ids: list[str],
    meta_by_id: dict,
    datasets: dict,
    hidden_ids: set[str],
    deleted_ids: set[str],
) -> dict:
    node_ids = [str(node_id) for node_id in node_ids if isinstance(node_id, str) and node_id]
    nodes: dict[str, dict] = {}
    edges: list[dict[str, str]] = []
    node_set = set(node_ids)
    for node_id in node_ids:
        node_meta = meta_by_id.get(node_id) if isinstance(meta_by_id, dict) else {}
        node_meta = node_meta if isinstance(node_meta, dict) else {}
        node_entry = datasets.get(node_id) if isinstance(datasets, dict) else {}
        node_entry = node_entry if isinstance(node_entry, dict) else {}
        parent_ids = _entry_parent_ids(node_entry)
        for parent_id in parent_ids:
            if parent_id in node_set:
                edges.append({"source": parent_id, "target": node_id})
        nodes[node_id] = {
            "id": node_id,
            "label": node_meta.get("label") or node_entry.get("label") or node_id,
            "stage": node_meta.get("stage") or node_entry.get("stage"),
            "transform_kind": node_meta.get("transform_kind"),
            "parent_ids": parent_ids,
            "schema_hash": node_entry.get("schema_hash"),
            "fingerprint": node_entry.get("fingerprint"),
            "created_ts": node_entry.get("created_ts"),
            "hidden": node_id in hidden_ids,
            "deleted": node_id in deleted_ids,
        }
    return {
        "pipeline_hash": pipeline_hash,
        "nodes": nodes,
        "edges": edges,
        "hidden_ids": sorted(hidden_ids),
        "deleted_ids": sorted(deleted_ids),
        "updated_ts": time.time(),
    }


def _apply_branch_ui_action(
    *,
    action: str,
    branch_ids: set[str],
    hidden_ids: set[str],
    deleted_ids: set[str],
) -> tuple[set[str], set[str], str]:
    hidden_ids = set(hidden_ids)
    deleted_ids = set(deleted_ids)
    branch_ids = {str(dataset_id) for dataset_id in branch_ids if isinstance(dataset_id, str) and dataset_id}
    normalized_action = action.strip().lower() if isinstance(action, str) else ""

    if normalized_action == "soft_delete":
        return hidden_ids, deleted_ids | branch_ids, "Soft-deleted"
    if normalized_action == "restore":
        return hidden_ids - branch_ids, deleted_ids - branch_ids, "Restored"
    if normalized_action == "hide":
        return hidden_ids | branch_ids, deleted_ids, "Hid"
    if normalized_action == "unhide":
        return hidden_ids - branch_ids, deleted_ids, "Unhid"
    raise ValueError(f"Unknown branch UI action: {action}")


def _pick_latest_dataset_id_for_datasets(datasets: dict) -> str | None:
    datasets = datasets if isinstance(datasets, dict) else {}
    best_dataset_id: str | None = None
    best_created_ts = float("-inf")
    for dataset_id, dataset_entry in datasets.items():
        if not isinstance(dataset_id, str) or not dataset_id or not isinstance(dataset_entry, dict):
            continue
        try:
            created_ts = float(dataset_entry.get("created_ts") or 0.0)
        except Exception:
            created_ts = 0.0
        if created_ts >= best_created_ts:
            best_created_ts = created_ts
            best_dataset_id = dataset_id
    if best_dataset_id:
        return best_dataset_id
    for dataset_id in datasets.keys():
        if isinstance(dataset_id, str) and dataset_id:
            return dataset_id
    return None


def _hard_delete_branch_from_team_state(
    *,
    team_state: dict,
    root_id: str,
) -> dict:
    root_id = root_id.strip() if isinstance(root_id, str) else ""
    if not root_id:
        return {"ok": False, "error": "Hard delete skipped: missing dataset id."}

    team_state = team_state if isinstance(team_state, dict) else {}
    datasets = team_state.get("datasets")
    datasets = datasets if isinstance(datasets, dict) else {}
    if root_id not in datasets:
        return {"ok": False, "error": f"Hard delete skipped: `{root_id}` not found."}

    children_index = _build_children_index(datasets)
    branch_ids = {root_id} | _descendants(root_id, children_index)
    remaining_datasets = {
        dataset_id: dataset_entry
        for dataset_id, dataset_entry in datasets.items()
        if dataset_id not in branch_ids
    }
    if not remaining_datasets:
        return {
            "ok": False,
            "error": "Hard delete skipped: would remove all datasets.",
        }

    active_dataset_id = team_state.get("active_dataset_id")
    active_dataset_id = (
        active_dataset_id
        if isinstance(active_dataset_id, str) and active_dataset_id
        else None
    )
    if active_dataset_id in branch_ids:
        active_dataset_id = _pick_latest_dataset_id_for_datasets(remaining_datasets)

    updated_team_state = dict(team_state)
    updated_team_state["datasets"] = remaining_datasets
    updated_team_state["active_dataset_id"] = active_dataset_id
    return {
        "ok": True,
        "team_state": updated_team_state,
        "branch_ids": branch_ids,
    }


def _normalize_readonly_sql(sql_text: str) -> str:
    sql_text = sql_text if isinstance(sql_text, str) else ""
    sql_text = sql_text.strip()
    if not sql_text:
        raise ValueError("SQL is empty; nothing to run.")

    parts = [part.strip() for part in sql_text.split(";")]
    non_empty_parts = [part for part in parts if part]
    if len(non_empty_parts) > 1:
        raise ValueError("Only single-statement queries are allowed.")
    sql_text = non_empty_parts[0] if non_empty_parts else ""
    first_token = re.sub(r"^\s*\(+\s*", "", sql_text).strip().lower()
    if not re.match(r"^(select|with|pragma|explain)\b", first_token):
        raise ValueError(
            "Only read-only queries are allowed (SELECT/WITH/PRAGMA/EXPLAIN)."
        )
    return sql_text


def _exec_python_merge_transform(
    *,
    code: str,
    parent_dfs: list[pd.DataFrame],
) -> pd.DataFrame:
    code = code if isinstance(code, str) else ""
    code = code.strip()
    if not code:
        raise ValueError("Merge code is empty; nothing to run.")

    parents_data = [df.to_dict() for df in parent_dfs]
    result, error = run_code_sandboxed_subprocess(
        code_snippet=code,
        function_name="merge",
        data=parents_data,
        timeout=60,
        memory_limit_mb=512,
        data_format="dataframe_list",
    )

    if error:
        raise ValueError(f"Merge execution error: {error}")

    output_data = None
    if result is not None:
        try:
            if isinstance(result, dict):
                output_data = pd.DataFrame.from_dict(result)
            elif isinstance(result, list):
                output_data = pd.DataFrame(result)
        except Exception:
            output_data = None

    if not isinstance(output_data, pd.DataFrame):
        raise ValueError("Merge code did not produce a pandas DataFrame.")
    return output_data


def _topological_order_for_stale_set(
    *,
    stale_set: set[str],
    parents_by_id: dict[str, list[str]],
    children_index: dict[str, set[str]],
    datasets: dict,
) -> list[str]:
    stale_set = {
        dataset_id for dataset_id in stale_set if isinstance(dataset_id, str) and dataset_id
    }
    if not stale_set:
        return []

    def _created_ts(dataset_id: str) -> float:
        dataset_entry = datasets.get(dataset_id) if isinstance(datasets, dict) else {}
        dataset_entry = dataset_entry if isinstance(dataset_entry, dict) else {}
        try:
            return float(dataset_entry.get("created_ts") or 0.0)
        except Exception:
            return 0.0

    indegree_by_id: dict[str, int] = {}
    for dataset_id in stale_set:
        indegree_by_id[dataset_id] = sum(
            1 for parent_id in parents_by_id.get(dataset_id, []) if parent_id in stale_set
        )
    queue = [dataset_id for dataset_id in stale_set if indegree_by_id.get(dataset_id, 0) == 0]
    queue.sort(key=_created_ts)
    ordered_dataset_ids: list[str] = []
    while queue:
        dataset_id = queue.pop(0)
        ordered_dataset_ids.append(dataset_id)
        for child_id in children_index.get(dataset_id, set()):
            if child_id not in stale_set:
                continue
            indegree_by_id[child_id] = max(0, int(indegree_by_id.get(child_id, 0)) - 1)
            if indegree_by_id[child_id] == 0:
                queue.append(child_id)
                queue.sort(key=_created_ts)
    if len(ordered_dataset_ids) < len(stale_set):
        remaining_ids = [
            dataset_id for dataset_id in stale_set if dataset_id not in set(ordered_dataset_ids)
        ]
        remaining_ids.sort(key=_created_ts)
        ordered_dataset_ids.extend(remaining_ids)
    return ordered_dataset_ids
