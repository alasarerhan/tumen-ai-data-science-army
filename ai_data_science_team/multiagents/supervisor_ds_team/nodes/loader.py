"""Auto-generated loader node module.

Extracted from the 3,400-line ``supervisor_ds_team.py`` monolith
during the L2 code-review remediation pass.  Uses dependency
injection via the ``LoaderNodeDeps`` dataclass.
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
    format_listing_with_llm,
    format_result_with_llm,
    merge_messages,
    register_dataset,
    tag_messages,
)

logger = logging.getLogger(__name__)


@dataclass
class LoaderNodeDeps:
    """Dependencies for the loader node."""
    data_loader_agent: Any
    ensure_dataset_registry: Any  # was _ensure_dataset_registry
    format_listing_with_llm: Any  # was _format_listing_with_llm
    format_result_with_llm: Any  # was _format_result_with_llm
    _get_last_human_text: Any  # was _get_last_human
    merge_messages: Any  # was _merge_messages
    register_dataset: Any  # was _register_dataset
    tag_messages: Any  # was _tag_messages
    llm: Any


def make_node_loader(deps: LoaderNodeDeps) -> Callable[[SupervisorDSState], dict]:
    """Build the ``node_loader`` state-graph node."""

    def node_loader(state: SupervisorDSState):
        logger.info("---DATA LOADER---")
        before_msgs = list(state.get("messages", []) or [])
        last_human = deps._get_last_human_text(before_msgs)
        cfg = (state.get("artifacts") or {}).get("config") or {}
        debug = bool(cfg.get("debug")) if isinstance(cfg, dict) else False
        if debug:
            logger.info(f"  loader last_human={last_human!r}")

        # DataLoaderToolsAgent is tool-driven; the latest user request is already in messages.
        deps.data_loader_agent.invoke_messages(messages=before_msgs)
        response = deps.data_loader_agent.response or {}
        merged = deps.merge_messages(before_msgs, response)

        loader_artifacts = response.get("data_loader_artifacts")
        if debug:
            try:
                logger.info(f"  loader response_keys={sorted(list(response.keys()))}")
                if isinstance(loader_artifacts, dict):
                    logger.info(
                        f"  loader artifacts_keys={list(loader_artifacts.keys())[:25]}"
                    )
                else:
                    logger.info(f"  loader artifacts_type={type(loader_artifacts)}")
            except Exception:
                pass

        previous_data_raw = state.get("data_raw")
        data_raw = previous_data_raw
        active_data_key = state.get("active_data_key")

        dir_listing = None
        loaded_dataset = None
        loaded_dataset_label = None
        multiple_loaded_files = None
        multiple_loaded_datasets: list[tuple[str, Any]] | None = None
        fallback_loaded_dataset = False
        multi_file_load = False

        artifacts_map = normalize_loader_artifacts(loader_artifacts)
        if debug:
            try:
                logger.info(f"  loader artifacts_map_keys={list(artifacts_map.keys())[:25]}")
            except Exception:
                pass

        (
            dir_listing,
            loaded_dataset,
            loaded_dataset_label,
            multiple_loaded_files,
            multiple_loaded_datasets,
            load_file_ok_items,
        ) = extract_loader_artifact_results(artifacts_map)

        if debug:
            try:
                logger.info(f"  loader load_file_ok_items={len(load_file_ok_items)}")
                for name, data in load_file_ok_items[:3]:
                    logger.info(
                        f"    - ok {name}: data_type={type(data)} shape={_shape(data)}"
                    )
            except Exception:
                pass

        # Fallback: if tool artifacts didn't yield usable data, load file paths directly from the user text.
        if (
            loaded_dataset is None
            and not multiple_loaded_datasets
            and not load_file_ok_items
            and isinstance(last_human, str)
            and last_human.strip()
        ):
            try:
                import re
                import pandas as pd

                from ai_data_science_team.tools.data_loader import (
                    auto_load_file,
                    DEFAULT_MAX_ROWS,
                )

                last_human_lower = last_human.lower()
                if any(
                    w in last_human_lower for w in ("load", "read", "import", "open")
                ):
                    requested = re.findall(
                        r"(?:`|\"|')?([^\s'\"`]+\.(?:csv|tsv|parquet|xlsx?|jsonl|ndjson|json)(?:\.gz)?)",
                        last_human,
                        flags=re.IGNORECASE,
                    )
                    requested = [r.strip() for r in requested if str(r).strip()]
                    seen_req: set[str] = set()
                    requested_unique: list[str] = []
                    for r in requested:
                        if r in seen_req:
                            continue
                        seen_req.add(r)
                        requested_unique.append(r)

                    ok_items: list[tuple[str, Any]] = []  # type: ignore[no-redef]
                    errs: list[str] = []
                    for fp in requested_unique:
                        df_or_error = auto_load_file(fp, max_rows=DEFAULT_MAX_ROWS)
                        if isinstance(df_or_error, pd.DataFrame):
                            ok_items.append((fp, df_or_error.to_dict()))
                        else:
                            errs.append(f"{fp}: {df_or_error}")

                    if ok_items:
                        multi_file_load = len(ok_items) > 1
                        multiple_loaded_files = [fp for fp, _ in ok_items]
                        multiple_loaded_datasets = ok_items
                        loaded_dataset_label, loaded_dataset = ok_items[-1]
                        fallback_loaded_dataset = True
                        dir_listing = None
                        if debug:
                            logger.info(
                                f"  loader deterministic_fallback_loaded={len(ok_items)} last={loaded_dataset_label!r}"
                            )
                    if errs and debug:
                        logger.info(f"  loader deterministic_fallback_errors={errs[:3]}")

                    if errs:
                        marker = {
                            "status": "error",
                            "data": None,
                            "error": "; ".join(errs[:3]),
                        }
                        if isinstance(loader_artifacts, dict):
                            loader_artifacts = {
                                **loader_artifacts,
                                "load_file_deterministic_fallback": marker,
                            }
                        elif loader_artifacts is None:
                            loader_artifacts = {
                                "load_file_deterministic_fallback": marker
                            }
            except Exception:
                pass

        # If multiple load_file calls succeeded, keep them all and default the active dataset to the last one.
        if (
            loaded_dataset is None
            and not multiple_loaded_datasets
            and len(load_file_ok_items) > 1
        ):
            labels = infer_requested_load_labels(last_human or "", load_file_ok_items)

            multi_file_load = True
            multiple_loaded_files = labels
            multiple_loaded_datasets = [
                (lbl, data) for lbl, (_name, data) in zip(labels, load_file_ok_items)
            ]
            loaded_dataset_label, loaded_dataset = multiple_loaded_datasets[-1]
        elif (
            loaded_dataset is None
            and not multiple_loaded_datasets
            and len(load_file_ok_items) == 1
        ):
            loaded_dataset_label, loaded_dataset = load_file_ok_items[0]

        # If the tool returned only a directory listing but the user requested a specific file to load,
        # attempt to load it deterministically (avoids "listing loop" regressions across turns).
        if loaded_dataset is None and dir_listing is not None:
            try:
                import re
                import os
                from pathlib import Path
                import pandas as pd

                from ai_data_science_team.tools.data_loader import (
                    auto_load_file,
                    DEFAULT_MAX_ROWS,
                )

                last_human_text = deps._get_last_human_text(before_msgs) or ""
                last_human_lower = last_human_text.lower()

                if any(
                    w in last_human_lower for w in ("load", "read", "import", "open")
                ):
                    m = re.search(
                        r"(?:`|\"|')?([^\s'\"`]+\.(?:csv|tsv|parquet|xlsx?|jsonl|ndjson|json)(?:\.gz)?)",
                        last_human_text,
                        flags=re.IGNORECASE,
                    )
                    requested_single: str = (m.group(1) if m else "").strip()
                    if requested_single:
                        p = Path(requested_single).expanduser()
                        if not p.is_absolute():
                            p = (Path(os.getcwd()) / p).resolve()
                        else:
                            p = p.resolve()

                        def _load_path(fp: str) -> Optional[dict]:
                            df_or_error = auto_load_file(fp, max_rows=DEFAULT_MAX_ROWS)
                            if isinstance(df_or_error, pd.DataFrame):
                                return df_or_error.to_dict()
                            return None

                        loaded = _load_path(str(p)) if p.is_file() else None

                        # If the path isn't directly valid, try to match by basename from listing outputs.
                        if loaded is None:
                            basename = Path(requested_single).name
                            candidate_paths: list[str] = []
                            if isinstance(dir_listing, list):
                                for item in dir_listing:
                                    if isinstance(item, dict):
                                        fp = (
                                            item.get("file_path")
                                            or item.get("absolute_path")
                                            or item.get("path")
                                            or item.get("filepath")
                                        )
                                        if isinstance(fp, str):
                                            candidate_paths.append(fp)
                                    elif isinstance(item, str):
                                        candidate_paths.append(item)
                            elif isinstance(dir_listing, dict):
                                for item in dir_listing.values():
                                    if isinstance(item, dict):
                                        fp = (
                                            item.get("file_path")
                                            or item.get("absolute_path")
                                            or item.get("path")
                                            or item.get("filepath")
                                        )
                                        if isinstance(fp, str):
                                            candidate_paths.append(fp)
                                    elif isinstance(item, str):
                                        candidate_paths.append(item)
                            for fp in candidate_paths:
                                try:
                                    resolved = Path(fp).expanduser().resolve()
                                except Exception:
                                    continue
                                if resolved.is_file() and resolved.name == basename:
                                    loaded = _load_path(str(resolved))
                                    if loaded is not None:
                                        loaded_dataset_label = str(resolved)
                                        break

                        if loaded is not None:
                            loaded_dataset = loaded
                            loaded_dataset_label = loaded_dataset_label or str(p)
                            dir_listing = None
                            fallback_loaded_dataset = True
            except Exception:
                pass

        if loaded_dataset is not None:
            data_raw = loaded_dataset
            active_data_key = "data_raw"
            # Prefer dataset summary over any incidental listings
            dir_listing = None
            if fallback_loaded_dataset:
                # The loader agent likely produced a listing-oriented AI message; suppress it.
                merged["messages"] = []
                # Store a lightweight marker so the supervisor can mark the load step as completed.
                marker = {
                    "status": "ok",
                    "data": {"file_path": str(loaded_dataset_label) if loaded_dataset_label is not None else None},  # type: ignore[dict-item]
                    "error": None,
                }
                if isinstance(loader_artifacts, dict):
                    loader_artifacts = {
                        **loader_artifacts,
                        "load_file_fallback": marker,
                    }
                else:
                    loader_artifacts = {"load_file_fallback": marker}

        logger.info(
            f"  loader data_raw shape={_shape(data_raw)} active_data_key={active_data_key}"
        )

        datasets, active_dataset_id = deps.ensure_dataset_registry(state)
        # Register newly loaded datasets in the dataset registry.
        if multi_file_load and multiple_loaded_datasets:
            try:
                import os
                from ai_data_science_team.tools.data_loader import (
                    resolve_existing_file_path,
                )

                state_for_register = {
                    **state,
                    "datasets": datasets,
                    "active_dataset_id": active_dataset_id,
                }
                to_register = list(multiple_loaded_datasets)[-DATASET_REGISTRY_MAX:]
                for idx, (fname, data) in enumerate(to_register):
                    source = str(fname)
                    try:
                        resolved_path, _matches = resolve_existing_file_path(source)
                        if resolved_path is not None:
                            source = str(resolved_path)
                    except Exception:
                        source = str(fname)

                    label = os.path.basename(source) or str(fname)
                    provenance = {
                        "source_type": "file",
                        "source": source or str(fname),
                        "original_name": os.path.basename(str(fname)) or str(fname),
                        "user_request": last_human,
                        "multi_load": True,
                    }
                    make_active = idx == (len(to_register) - 1)
                    datasets, active_dataset_id, _did = deps.register_dataset(
                        state_for_register,  # type: ignore[arg-type]
                        data=data,
                        stage="raw",
                        label=str(label),
                        created_by="Data_Loader_Tools_Agent",
                        provenance=provenance,
                        parent_id=None,
                        make_active=make_active,
                    )
                    state_for_register = {
                        **state_for_register,
                        "datasets": datasets,
                        "active_dataset_id": active_dataset_id,
                    }
            except Exception:
                # Never fail the load step due to registry bookkeeping.
                pass
        elif loaded_dataset is not None:
            try:
                import os

                # Best-effort: capture the file path from the user request for reproducibility.
                source = loaded_dataset_label
                try:
                    import re
                    from ai_data_science_team.tools.data_loader import (
                        resolve_existing_file_path,
                    )

                    if not (
                        isinstance(source, str)
                        and ("." in source and os.path.sep in source)
                    ):
                        m = re.search(
                            r"(?:`|\"|')?([^\s'\"`]+\.(?:csv|tsv|parquet|xlsx?|jsonl|ndjson|json)(?:\.gz)?)",
                            last_human or "",
                            flags=re.IGNORECASE,
                        )
                        requested_src: str = (m.group(1) if m else "").strip()
                        if requested_src:
                            resolved_path, _matches = resolve_existing_file_path(
                                requested_src
                            )
                            if resolved_path is not None:
                                source = str(resolved_path)
                            else:
                                source = requested_src
                    # Also normalize/absolutize an existing-looking path label.
                    if isinstance(source, str) and source.strip():
                        resolved_path, _matches = resolve_existing_file_path(source)
                        if resolved_path is not None:
                            source = str(resolved_path)
                except Exception:
                    pass

                label = source or loaded_dataset_label or "data_raw"
                if isinstance(label, str):
                    label = os.path.basename(label) or label
                provenance = {
                    "source_type": "file",
                    "source": source or loaded_dataset_label,
                    "original_name": os.path.basename(
                        str(source or loaded_dataset_label or "")
                    )
                    or None,
                    "user_request": last_human,
                    "fallback_loader": bool(fallback_loaded_dataset),
                }
                datasets, active_dataset_id, _did = deps.register_dataset(
                    {  # type: ignore[arg-type]
                        **state,
                        "datasets": datasets,
                        "active_dataset_id": active_dataset_id,
                    },
                    data=data_raw,
                    stage="raw",
                    label=str(label),
                    created_by="Data_Loader_Tools_Agent",
                    provenance=provenance,
                    parent_id=None,
                    make_active=True,
                )
            except Exception:
                # Never fail the load step due to registry bookkeeping.
                pass
        elif multiple_loaded_datasets:
            # Keep the already-loaded datasets available for explicit selection, but do not auto-switch.
            try:
                state_for_register = {
                    **state,
                    "datasets": datasets,
                    "active_dataset_id": active_dataset_id,
                }
                # Register only the most recent N to avoid unbounded growth.
                for fname, data in list(multiple_loaded_datasets)[
                    -DATASET_REGISTRY_MAX:
                ]:
                    datasets, active_dataset_id, _did = deps.register_dataset(
                        state_for_register,  # type: ignore[arg-type]
                        data=data,
                        stage="raw",
                        label=str(fname),
                        created_by="Data_Loader_Tools_Agent",
                        provenance={
                            "source_type": "directory_load",
                            "source": fname,
                            "user_request": last_human,
                        },
                        parent_id=None,
                        make_active=False,
                    )
                    state_for_register = {
                        **state_for_register,
                        "datasets": datasets,
                        "active_dataset_id": active_dataset_id,
                    }
            except Exception:
                pass

        # Add a lightweight AI summary message so supervisor can progress
        summary_msg = None
        if multi_file_load and multiple_loaded_datasets:
            try:
                import os
                import pandas as pd

                lines = []
                for fname, data in multiple_loaded_datasets:
                    label = os.path.basename(str(fname)) or str(fname)
                    shape_txt = ""
                    try:
                        df = pd.DataFrame(data)
                        shape_txt = f" ({df.shape[0]} rows × {df.shape[1]} cols)"
                    except Exception:
                        pass
                    lines.append(f"- {label}{shape_txt}")

                active_label = os.path.basename(str(loaded_dataset_label)) or str(
                    loaded_dataset_label or ""
                )
                preview_txt = ""
                try:
                    df_active = (
                        pd.DataFrame(data_raw) if isinstance(data_raw, dict) else None
                    )
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

                summary_msg = AIMessage(
                    content=(
                        f"Loaded {len(multiple_loaded_datasets)} datasets:\n\n"
                        + "\n".join(lines)
                        + (
                            f"\n\nActive dataset: {active_label}."
                            if active_label
                            else ""
                        )
                        + preview_txt
                        + "\n\nUse the sidebar dataset selector to switch the active dataset, or use Pipeline Studio to merge them."
                    ),
                    name="data_loader_agent",
                )
            except Exception:
                summary_msg = AIMessage(
                    content=(
                        f"Loaded {len(multiple_loaded_datasets)} datasets. "
                        "Use the sidebar dataset selector to switch the active dataset, or use Pipeline Studio to merge them."
                    ),
                    name="data_loader_agent",
                )
            summary_msg = summarize_multi_loaded_datasets(
                multiple_loaded_datasets,
                loaded_dataset_label,
                data_raw,
            )
        elif multiple_loaded_files:
            summary_msg = summarize_multiple_loaded_files(multiple_loaded_files)
        elif dir_listing is not None:
            try:
                # dir_listing could be list/dict; extract filenames
                names = []
                rows = []
                if isinstance(dir_listing, list):
                    for item in dir_listing:
                        if isinstance(item, dict):
                            if "filename" in item:
                                names.append(item.get("filename"))
                                rows.append(
                                    {
                                        "filename": item.get("filename"),
                                        "type": item.get("type"),
                                        "path": item.get("path")
                                        or item.get("filepath"),
                                    }
                                )
                                continue
                            if "file_path" in item:
                                fp = item.get("file_path")
                                import os

                                fn = (
                                    os.path.basename(fp)
                                    if isinstance(fp, str)
                                    else str(fp)
                                )
                                names.append(fn)
                                rows.append(
                                    {"filename": fn, "type": "file", "path": fp}
                                )
                                continue
                            if "absolute_path" in item or "name" in item:
                                ap = item.get("absolute_path")
                                import os

                                fn = item.get("name") or (
                                    os.path.basename(ap)
                                    if isinstance(ap, str)
                                    else str(ap)
                                )
                                names.append(fn)
                                rows.append(
                                    {
                                        "filename": fn,
                                        "type": item.get("type"),
                                        "path": ap,
                                    }
                                )
                                continue

                        names.append(str(item))
                        rows.append({"filename": str(item)})
                elif isinstance(dir_listing, dict):
                    # maybe mapping index->filename
                    for v in dir_listing.values():
                        if isinstance(v, dict):
                            if "filename" in v:
                                names.append(str(v.get("filename")))
                                rows.append(
                                    {
                                        "filename": v.get("filename"),
                                        "type": v.get("type"),
                                        "path": v.get("path") or v.get("filepath"),
                                    }
                                )
                            elif "file_path" in v:
                                fp = v.get("file_path")
                                import os

                                fn = (
                                    os.path.basename(fp)
                                    if isinstance(fp, str)
                                    else str(fp)
                                )
                                names.append(fn)
                                rows.append(
                                    {"filename": fn, "type": "file", "path": fp}
                                )
                            elif "absolute_path" in v or "name" in v:
                                ap = v.get("absolute_path")
                                import os

                                fn = v.get("name") or (
                                    os.path.basename(ap)
                                    if isinstance(ap, str)
                                    else str(ap)
                                )
                                names.append(fn)
                                rows.append(
                                    {"filename": fn, "type": v.get("type"), "path": ap}
                                )
                            else:
                                names.append(str(v))
                                rows.append({"filename": str(v)})
                        else:
                            names.append(str(v))
                            rows.append({"filename": str(v)})

                last_human = deps._get_last_human_text(before_msgs).lower()
                wants_csv_only = "csv" in last_human and (
                    "list" in last_human or "files" in last_human
                )
                if wants_csv_only and rows:
                    rows = [
                        r
                        for r in rows
                        if str(r.get("filename", "")).lower().endswith(".csv")
                    ]
                    names = [r.get("filename") for r in rows if r.get("filename")]
                    if not rows:
                        summary_msg = AIMessage(
                            content="No CSV files found in that directory.",
                            name="data_loader_agent",
                        )
                        dir_listing = None

                if summary_msg is None:
                    msg_text = (
                        "Found files: " + ", ".join(names)
                        if names
                        else "Found directory contents."
                    )
                    table_text = ""
                    if rows:
                        import pandas as pd

                        df_listing = pd.DataFrame(rows)
                        table_cols = [
                            c
                            for c in ["filename", "type", "path"]
                            if c in df_listing.columns
                        ]
                        table_text = df_listing[table_cols].to_markdown(index=False)
                    # If the user asked for a table or better formatting, try a tiny LLM summary
                    llm_text = (
                        deps.format_listing_with_llm(rows, last_human) if rows else None
                    )
                    if llm_text:
                        summary_msg = AIMessage(
                            content=llm_text, name="data_loader_agent"
                        )
                    elif table_text:
                        summary_msg = AIMessage(
                            content=f"{msg_text}\n\n{table_text}",
                            name="data_loader_agent",
                        )
                    else:
                        summary_msg = AIMessage(
                            content=msg_text, name="data_loader_agent"
                        )
            except Exception:
                summary_msg = AIMessage(
                    content="Listed directory contents.", name="data_loader_agent"
                )
            summary_msg, dir_listing = summarize_directory_listing(
                dir_listing,
                (deps._get_last_human_text(before_msgs) or "").lower(),
                deps.format_listing_with_llm,
            )
        elif loaded_dataset is not None and isinstance(data_raw, dict):
            summary_msg = summarize_loaded_dataset(
                data_raw,
                (deps._get_last_human_text(before_msgs) or "").lower(),
                deps.format_result_with_llm,
            )
        elif loader_artifacts is not None:
            summary_msg = summarize_loader_failure(loader_artifacts)

        if summary_msg:
            merged["messages"] = merged.get("messages", []) + [summary_msg]

        loader_errors = collect_loader_errors(loader_artifacts)
        if loader_errors:
            merged["messages"] = merged.get("messages", []) + [
                AIMessage(
                    content="Data loading error(s):\n" + "\n".join(loader_errors),
                    name="data_loader_agent",
                )
            ]

        merged["messages"] = deps.tag_messages(merged.get("messages"), "data_loader_agent")

        # If the dataset changed, clear downstream artifacts to avoid stale plots/models.
        downstream_resets = {}
        if loaded_dataset is not None:
            downstream_resets = {
                "data_wrangled": None,
                "data_cleaned": None,
                "eda_artifacts": None,
                "viz_graph": None,
                "feature_data": None,
                "model_info": None,
                "mlflow_artifacts": None,
            }

        return {
            **merged,
            "data_raw": data_raw,
            "active_data_key": active_data_key,
            "datasets": datasets,
            "active_dataset_id": active_dataset_id,
            "artifacts": {
                **state.get("artifacts", {}),
                "data_loader": loader_artifacts,
                "data_loader_details": {"errors": loader_errors} if loader_errors else {},
            },
            "last_worker": "Data_Loader_Tools_Agent",
            **downstream_resets,
        }


    return node_loader



__all__ = ["LoaderNodeDeps", "make_node_loader"]
