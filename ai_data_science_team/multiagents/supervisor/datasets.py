from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

DATASET_REGISTRY_MAX = 10
DATASET_FINGERPRINT_MAX_ROWS = 200
DATASET_SCHEMA_MAX_COLS = 200


def ensure_df(data: Any):
    try:
        import pandas as pd  # noqa: E402, F401

        if data is None:
            return None
        if isinstance(data, dict):
            return pd.DataFrame(data)
        if isinstance(data, list):
            return pd.DataFrame(data)
        return data
    except Exception:
        return data


def shape_of(obj: Any):
    try:
        import pandas as pd  # noqa: E402, F401

        if isinstance(obj, pd.DataFrame):
            return obj.shape
        if isinstance(obj, dict):
            return (len(obj), len(next(iter(obj.values()))) if obj else 0)
        if isinstance(obj, list):
            return (len(obj),)
    except Exception:
        return None
    return None


def dataset_meta(
    data: Any,
) -> tuple[Any, list[str] | None, list[dict[str, str]] | None, str | None, str | None]:
    df = ensure_df(data)
    shape = shape_of(df)
    columns = None
    schema = None
    schema_hash = None
    fingerprint = None
    try:
        columns = [str(column) for column in list(getattr(df, "columns", []))]
        columns = columns[:DATASET_SCHEMA_MAX_COLS] if columns else None
    except Exception:
        columns = None

    try:
        import hashlib  # noqa: E402, F401

        import pandas as pd  # noqa: E402, F401

        if isinstance(df, pd.DataFrame):
            column_order = sorted([str(column) for column in list(df.columns)])
            schema = [
                {
                    "name": column,
                    "dtype": str(df[column].dtype) if column in df.columns else "",
                }
                for column in column_order[:DATASET_SCHEMA_MAX_COLS]
            ]
            schema_str = "|".join(f"{row['name']}:{row['dtype']}" for row in schema)
            schema_hash = (
                hashlib.sha256(schema_str.encode("utf-8")).hexdigest() if schema_str else None
            )

            df_sample = (
                df.reindex(columns=column_order)
                .head(DATASET_FINGERPRINT_MAX_ROWS)
                .reset_index(drop=True)
            )
            try:
                from pandas.util import hash_pandas_object  # noqa: E402, F401

                row_hashes = hash_pandas_object(df_sample, index=False).values
                fingerprint = hashlib.sha256(row_hashes.tobytes()).hexdigest()
            except Exception:
                snapshot = df_sample.to_json(orient="split", date_format="iso")
                fingerprint = hashlib.sha256(snapshot.encode("utf-8")).hexdigest()
    except Exception:
        schema = None
        schema_hash = None
        fingerprint = None

    return shape, columns, schema, schema_hash, fingerprint


def truncate_text(val: Any, max_chars: int) -> Any:
    if not isinstance(val, str):
        return val
    if len(val) <= max_chars:
        return val
    return val[:max_chars] + "\n...[truncated]..."


def sha256_text(val: Any) -> str | None:
    try:
        import hashlib  # noqa: E402, F401

        if not isinstance(val, str) or not val:
            return None
        return hashlib.sha256(val.encode("utf-8")).hexdigest()
    except Exception:
        return None


def prune_datasets(datasets: dict[str, Any]) -> dict[str, Any]:
    if len(datasets) <= DATASET_REGISTRY_MAX:
        return datasets
    items: list[tuple[float, str]] = []
    for dataset_id, entry in datasets.items():
        timestamp = 0.0
        if isinstance(entry, dict):
            try:
                timestamp = float(entry.get("created_ts") or 0.0)
            except Exception:
                timestamp = 0.0
        items.append((timestamp, dataset_id))
    items.sort(reverse=True)
    keep = {dataset_id for _timestamp, dataset_id in items[:DATASET_REGISTRY_MAX]}
    return {dataset_id: datasets[dataset_id] for dataset_id in keep if dataset_id in datasets}


def ensure_dataset_registry(state: Mapping[str, Any]) -> tuple[dict[str, Any], str | None]:
    datasets = state.get("datasets")
    datasets = datasets if isinstance(datasets, dict) else {}
    active_id = state.get("active_dataset_id")
    active_id = active_id if isinstance(active_id, str) else None

    if not datasets:
        import time  # noqa: E402, F401
        import uuid  # noqa: E402, F401
        from datetime import datetime, timezone  # noqa: E402, F401

        def add_dataset(stage: str, data_key: str):
            nonlocal datasets
            data = state.get(data_key)
            if data is None:
                return
            dataset_id = f"{stage}_{uuid.uuid4().hex[:8]}"
            shape, columns, schema, schema_hash, fingerprint = dataset_meta(data)
            timestamp = time.time()
            provenance = {"source_type": "state_slot", "source": data_key}
            if stage == "raw" and data_key == "data_raw":
                try:
                    artifacts = state.get("artifacts") or {}
                    input_dataset = (
                        artifacts.get("input_dataset") if isinstance(artifacts, dict) else None
                    )
                    if isinstance(input_dataset, dict) and input_dataset.get("source"):
                        provenance = {**provenance, **input_dataset}
                except Exception:
                    pass

            datasets[dataset_id] = {
                "id": dataset_id,
                "label": data_key,
                "stage": stage,
                "data": data,
                "shape": shape,
                "columns": columns,
                "schema": schema,
                "schema_hash": schema_hash,
                "fingerprint": fingerprint,
                "created_ts": timestamp,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": "bootstrap",
                "provenance": provenance,
                "parent_id": None,
                "parent_ids": [],
            }

        add_dataset("raw", "data_raw")
        add_dataset("sql", "data_sql")
        add_dataset("wrangled", "data_wrangled")
        add_dataset("cleaned", "data_cleaned")
        add_dataset("feature", "feature_data")

    if active_id is None and datasets:
        active_key = state.get("active_data_key")
        stage_for_key = {
            "data_raw": "raw",
            "data_sql": "sql",
            "data_wrangled": "wrangled",
            "data_cleaned": "cleaned",
            "feature_data": "feature",
        }.get(active_key)
        if stage_for_key:
            matching = [
                dataset_id
                for dataset_id, entry in datasets.items()
                if isinstance(entry, dict) and entry.get("stage") == stage_for_key
            ]
            if matching:
                active_id = matching[-1]
        if active_id is None:
            newest = sorted(
                datasets.items(),
                key=lambda kv: (
                    float(kv[1].get("created_ts") or 0.0) if isinstance(kv[1], dict) else 0.0
                ),
            )
            active_id = newest[-1][0] if newest else None

    if active_id is not None and active_id not in datasets:
        active_id = None

    return prune_datasets(datasets), active_id


def register_dataset(
    state: Mapping[str, Any],
    *,
    data: Any,
    stage: str,
    label: str,
    created_by: str,
    provenance: dict[str, Any],
    parent_id: str | None = None,
    parent_ids: Sequence[str] | None = None,
    make_active: bool = True,
) -> tuple[dict[str, Any], str | None, str]:
    import time  # noqa: E402, F401
    import uuid  # noqa: E402, F401
    from datetime import datetime, timezone  # noqa: E402, F401

    datasets, current_active = ensure_dataset_registry(state)
    dataset_id = f"{stage}_{uuid.uuid4().hex[:8]}"
    shape, columns, schema, schema_hash, fingerprint = dataset_meta(data)
    timestamp = time.time()
    normalized_parents: list[str] = []
    if isinstance(parent_ids, (list, tuple)):
        normalized_parents = [
            str(parent) for parent in parent_ids if isinstance(parent, str) and parent
        ]
    if parent_id and parent_id not in normalized_parents:
        normalized_parents = [parent_id, *normalized_parents]
    normalized_parents = [parent for parent in normalized_parents if parent]
    parent_id = normalized_parents[0] if normalized_parents else parent_id
    datasets = {
        **datasets,
        dataset_id: {
            "id": dataset_id,
            "label": label or dataset_id,
            "stage": stage,
            "data": data,
            "shape": shape,
            "columns": columns,
            "schema": schema,
            "schema_hash": schema_hash,
            "fingerprint": fingerprint,
            "created_ts": timestamp,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": created_by,
            "provenance": provenance or {},
            "parent_id": parent_id,
            "parent_ids": normalized_parents,
        },
    }
    datasets = prune_datasets(datasets)
    active_id = dataset_id if make_active else current_active
    return datasets, active_id, dataset_id


def get_active_data(state: Mapping[str, Any], fallback_keys: Sequence[str]):
    datasets = state.get("datasets")
    active_id = state.get("active_dataset_id")
    if isinstance(datasets, dict) and isinstance(active_id, str):
        entry = datasets.get(active_id)
        if isinstance(entry, dict) and entry.get("data") is not None:
            return entry.get("data")
    active_key = state.get("active_data_key")
    if active_key and state.get(active_key) is not None:
        return state.get(active_key)
    for key in fallback_keys:
        if state.get(key) is not None:
            return state.get(key)
    return None


def is_empty_df(df: Any) -> bool:
    try:
        return df is None or bool(getattr(df, "empty", False))
    except Exception:
        return df is None
