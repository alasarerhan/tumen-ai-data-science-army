from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def parse_list_value(val: Any) -> list[str]:
    if isinstance(val, list):
        return [str(item).strip() for item in val if str(item).strip()]
    if isinstance(val, tuple):
        return [str(item).strip() for item in val if str(item).strip()]
    if isinstance(val, str):
        return [part for part in (piece.strip() for piece in val.split(",")) if part]
    return []


def dedupe_keep_order(items: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def resolve_dataset_ids_from_text(
    datasets: Mapping[str, Any],
    text: str,
) -> list[str]:
    if not text:
        return []
    lowered = text.lower()
    matches: list[str] = []
    for dataset_id, entry in datasets.items():
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("label") or "").lower()
        provenance = entry.get("provenance") if isinstance(entry.get("provenance"), dict) else {}
        original = str(provenance.get("original_name") or "").lower()
        source = str(provenance.get("source") or "").lower()
        if dataset_id.lower() in lowered:
            matches.append(dataset_id)
            continue
        if label and label in lowered:
            matches.append(dataset_id)
            continue
        if original and original in lowered:
            matches.append(dataset_id)
            continue
        if source and source in lowered:
            matches.append(dataset_id)
            continue
    return matches


def resolve_selected_dataset_ids(
    datasets: Mapping[str, Any],
    active_dataset_id: str | None,
    merge_cfg: Mapping[str, Any],
    last_human: str,
) -> list[str]:
    selected_ids = parse_list_value(merge_cfg.get("dataset_ids"))
    selected_ids = [dataset_id for dataset_id in selected_ids if dataset_id in datasets]

    if len(selected_ids) < 2:
        inferred = resolve_dataset_ids_from_text(datasets, last_human)
        selected_ids = [*selected_ids, *inferred]

    if len(selected_ids) < 2 and active_dataset_id and active_dataset_id in datasets:
        selected_ids = [active_dataset_id]
        ordered = sorted(
            datasets.items(),
            key=lambda item: (
                float(item[1].get("created_ts") or 0.0) if isinstance(item[1], dict) else 0.0
            ),
            reverse=True,
        )
        for dataset_id, _entry in ordered:
            if dataset_id != active_dataset_id:
                selected_ids.append(dataset_id)
                break

    return dedupe_keep_order([dataset_id for dataset_id in selected_ids if dataset_id in datasets])


def available_datasets_lines(datasets: Mapping[str, Any], limit: int = 10) -> list[str]:
    available: list[str] = []
    ordered = sorted(
        datasets.items(),
        key=lambda item: (
            float(item[1].get("created_ts") or 0.0) if isinstance(item[1], dict) else 0.0
        ),
        reverse=True,
    )
    for dataset_id, entry in ordered[:limit]:
        if not isinstance(entry, dict):
            continue
        available.append(f"- `{dataset_id}` ({entry.get('stage')}:{entry.get('label')})")
    return available
