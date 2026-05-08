import os
import json
import uuid
import time
import shutil
import tempfile
import re
import logging
from typing import Dict, Any, Optional, List

import pandas as pd

from ai_data_science_team.constants import PipelineStudioLimits
from ai_data_science_team.exceptions import ProjectNotFoundError, ProjectSaveError

logger = logging.getLogger(__name__)


APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
PIPELINE_STUDIO_PROJECTS_DIR = os.path.join(APP_ROOT, "pipeline_store", "pipeline_projects")
PIPELINE_STUDIO_PROJECTS_VERSION = 1


def project_slug(name: str) -> str:
    name = name.strip() if isinstance(name, str) else ""
    name = re.sub(r"[^a-zA-Z0-9_-]+", "-", name).strip("-_")
    name = re.sub(r"-{2,}", "-", name).strip("-_")
    return name.lower() if name else "project"


def load_project_manifest(*, project_dir: str) -> Optional[dict]:
    project_dir = project_dir.strip() if isinstance(project_dir, str) else ""
    if not project_dir:
        return None
    manifest_path = os.path.join(project_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        return None
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        logger.warning("Failed to load project manifest from %s: %s", manifest_path, e)
        return None
    return manifest if isinstance(manifest, dict) else None


def write_project_manifest(*, project_dir: str, manifest: dict) -> bool:
    try:
        project_dir = project_dir.strip() if isinstance(project_dir, str) else ""
        if not project_dir or not isinstance(manifest, dict):
            return False
        manifest_path = os.path.join(project_dir, "manifest.json")
        fd, tmp_path = tempfile.mkstemp(prefix="._manifest_", suffix=".json", dir=project_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, default=str)
            os.replace(tmp_path, manifest_path)
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception as e:
                logger.warning("Failed to cleanup temp manifest file %s: %s", tmp_path, e)
        return True
    except Exception as e:
        logger.error("Failed to write project manifest to %s: %s", project_dir, e)
        return False


def update_project_manifest(
    *,
    project_dir: str,
    updates: Optional[dict] = None,
    dataset_source_updates: Optional[Dict[str, str]] = None,
) -> Optional[dict]:
    manifest = load_project_manifest(project_dir=project_dir)
    if not isinstance(manifest, dict):
        return None
    updates = updates if isinstance(updates, dict) else {}
    if updates:
        manifest.update(updates)
    if isinstance(dataset_source_updates, dict) and dataset_source_updates:
        team = manifest.get("team_state")
        team = team if isinstance(team, dict) else {}
        datasets_meta = team.get("datasets")
        datasets_meta = datasets_meta if isinstance(datasets_meta, dict) else {}
        for did, new_source in dataset_source_updates.items():
            if not isinstance(did, str) or not did:
                continue
            if not isinstance(new_source, str) or not new_source.strip():
                continue
            entry = datasets_meta.get(did)
            entry = entry if isinstance(entry, dict) else {}
            prov = entry.get("provenance")
            prov = prov if isinstance(prov, dict) else {}
            prov["source"] = new_source.strip()
            prov["source_type"] = prov.get("source_type") or "file"
            entry["provenance"] = prov
            datasets_meta[did] = entry
        team["datasets"] = datasets_meta
        manifest["team_state"] = team
    write_project_manifest(project_dir=project_dir, manifest=manifest)
    return manifest


def list_projects() -> List[dict]:
    try:
        root = PIPELINE_STUDIO_PROJECTS_DIR
        if not os.path.isdir(root):
            return []
        items: List[dict] = []
        for dir_name in os.listdir(root):
            if not isinstance(dir_name, str) or not dir_name:
                continue
            dir_path = os.path.join(root, dir_name)
            if not os.path.isdir(dir_path):
                continue
            manifest = load_project_manifest(project_dir=dir_path)
            if not isinstance(manifest, dict):
                continue
            try:
                saved_ts = float(manifest.get("saved_ts") or manifest.get("created_ts") or 0.0)
            except Exception as e:
                logger.debug("Failed to parse saved_ts for %s: %s", dir_name, e)
                saved_ts = 0.0
            try:
                last_opened_ts = float(manifest.get("last_opened_ts") or 0.0)
            except Exception as e:
                logger.debug("Failed to parse last_opened_ts for %s: %s", dir_name, e)
                last_opened_ts = 0.0
            datasets_total = manifest.get("datasets_total")
            if not datasets_total:
                team_state = manifest.get("team_state")
                team_state = team_state if isinstance(team_state, dict) else {}
                ds_meta = team_state.get("datasets")
                ds_meta = ds_meta if isinstance(ds_meta, dict) else {}
                datasets_total = len(ds_meta)
            data_mode = manifest.get("data_mode")
            if not data_mode:
                team_state = manifest.get("team_state")
                team_state = team_state if isinstance(team_state, dict) else {}
                ds_meta = team_state.get("datasets")
                ds_meta = ds_meta if isinstance(ds_meta, dict) else {}
                data_mode = (
                    "full"
                    if any(
                        isinstance(rec, dict) and rec.get("data_path")
                        for rec in ds_meta.values()
                    )
                    else "metadata_only"
                )
            items.append({
                "dir_name": dir_name,
                "dir_path": dir_path,
                "manifest_path": os.path.join(dir_path, "manifest.json"),
                "saved_ts": saved_ts,
                "last_opened_ts": last_opened_ts,
                "name": manifest.get("name") if isinstance(manifest.get("name"), str) else dir_name,
                "pipeline_hash": manifest.get("pipeline_hash") if isinstance(manifest.get("pipeline_hash"), str) else "",
                "data_mode": data_mode or "full",
                "datasets_total": datasets_total or 0,
                "datasets_saved": manifest.get("datasets_saved") or 0,
                "tags": manifest.get("tags") or [],
                "notes": manifest.get("notes") or "",
                "archived": bool(manifest.get("archived", False)),
                "manifest": manifest,
            })
        items.sort(key=lambda x: float(x.get("saved_ts") or 0.0), reverse=True)
        return items
    except Exception as e:
        logger.error("Failed to list projects: %s", e)
        return []


def save_project(
    *,
    name: str,
    team_state: dict,
    include_data: bool = False,
    project_dir: Optional[str] = None,
) -> dict:
    try:
        team_state = team_state if isinstance(team_state, dict) else {}
        datasets = team_state.get("datasets")
        datasets = datasets if isinstance(datasets, dict) else {}
        active_id = team_state.get("active_dataset_id")
        active_id = active_id if isinstance(active_id, str) and active_id else None
        
        existing_manifest = None
        if isinstance(project_dir, str) and project_dir.strip():
            project_dir = project_dir.strip()
            os.makedirs(project_dir, exist_ok=True)
            dir_name = os.path.basename(project_dir.rstrip(os.sep)) or "project"
            existing_manifest = load_project_manifest(project_dir=project_dir)
            if isinstance(existing_manifest, dict):
                existing_dir = existing_manifest.get("dir_name")
                if isinstance(existing_dir, str) and existing_dir:
                    dir_name = existing_dir
            ds_dir = os.path.join(project_dir, "datasets")
            if os.path.isdir(ds_dir):
                shutil.rmtree(ds_dir, ignore_errors=True)
            if include_data:
                os.makedirs(ds_dir, exist_ok=True)
        else:
            os.makedirs(PIPELINE_STUDIO_PROJECTS_DIR, exist_ok=True)
            slug = project_slug(name)
            ts = int(time.time())
            dir_name = f"{slug}_{ts}"
            project_dir = os.path.join(PIPELINE_STUDIO_PROJECTS_DIR, dir_name)
            if os.path.exists(project_dir):
                dir_name = f"{slug}_{ts}_{uuid.uuid4().hex[:6]}"
                project_dir = os.path.join(PIPELINE_STUDIO_PROJECTS_DIR, dir_name)
            os.makedirs(project_dir, exist_ok=True)
            if include_data:
                ds_dir = os.path.join(project_dir, "datasets")
                os.makedirs(ds_dir, exist_ok=True)
        
        datasets_out: Dict[str, dict] = {}
        saved_count = 0
        
        for did, entry in datasets.items():
            if not isinstance(did, str) or not did:
                continue
            entry = entry if isinstance(entry, dict) else {}
            data = entry.get("data")
            df: Optional[pd.DataFrame] = None
            try:
                if isinstance(data, pd.DataFrame):
                    df = data
                elif isinstance(data, dict):
                    df = pd.DataFrame.from_dict(data)
                elif isinstance(data, list):
                    df = pd.DataFrame(data)
            except Exception:
                df = None
            meta = {k: v for k, v in entry.items() if k != "data"}
            if not include_data:
                meta.pop("data_path", None)
                meta.pop("data_format", None)
                meta.pop("data_bytes", None)
            meta["data_saved"] = False
            if include_data and df is not None:
                rel_path = os.path.join("datasets", f"{did}.parquet")
                abs_path = os.path.join(project_dir, rel_path)
                saved = _write_parquet(df, abs_path)
                if saved:
                    meta["data_path"] = rel_path
                    meta["data_format"] = "parquet"
                    meta["data_saved"] = True
                    saved_count += 1
                else:
                    rel_path = os.path.join("datasets", f"{did}.pkl")
                    abs_path = os.path.join(project_dir, rel_path)
                    df.to_pickle(abs_path)
                    meta["data_path"] = rel_path
                    meta["data_format"] = "pickle"
                    meta["data_saved"] = True
                    saved_count += 1
            datasets_out[did] = meta
        
        prev_tags: List[str] = []
        prev_notes = ""
        prev_archived = False
        prev_last_opened = None
        prev_created_ts = None
        if isinstance(existing_manifest, dict):
            tags_val = existing_manifest.get("tags")
            if isinstance(tags_val, list):
                prev_tags = tags_val
            notes_val = existing_manifest.get("notes")
            if isinstance(notes_val, str):
                prev_notes = notes_val
            prev_archived = bool(existing_manifest.get("archived", False))
            prev_last_opened = existing_manifest.get("last_opened_ts")
            prev_created_ts = existing_manifest.get("created_ts")
        
        manifest = {
            "version": PIPELINE_STUDIO_PROJECTS_VERSION,
            "name": name.strip() if isinstance(name, str) and name.strip() else dir_name,
            "saved_ts": time.time(),
            "dir_name": dir_name,
            "data_mode": "full" if include_data else "metadata_only",
            "datasets_saved": int(saved_count),
            "datasets_total": int(len(datasets_out)),
            "tags": prev_tags,
            "notes": prev_notes,
            "archived": prev_archived,
            "last_opened_ts": prev_last_opened,
            "team_state": {
                "active_dataset_id": active_id,
                "datasets": datasets_out,
            },
        }
        if prev_created_ts:
            manifest["created_ts"] = prev_created_ts
        
        write_project_manifest(project_dir=project_dir, manifest=manifest)
        _prune_projects(max_items=PipelineStudioLimits.PROJECTS_MAX_ITEMS)
        
        return {
            "project_dir": project_dir,
            "manifest_path": os.path.join(project_dir, "manifest.json"),
            "dir_name": dir_name,
        }
    except Exception as e:
        return {"error": str(e)}


def _write_parquet(df: pd.DataFrame, path: str) -> bool:
    try:
        for compression in ("zstd", "snappy", "gzip", None):
            try:
                df.to_parquet(path, index=False, compression=compression)
                return True
            except Exception:
                continue
    except Exception as e:
        logger.warning("Failed to write parquet to %s: %s", path, e)
    return False


def _prune_projects(*, max_items: int) -> None:
    try:
        import shutil
        max_items = int(max_items or 0)
        if max_items <= 0:
            return
        projects = list_projects()
        if len(projects) <= max_items:
            return
        for rec in projects[max_items:]:
            dir_path = rec.get("dir_path")
            if isinstance(dir_path, str) and dir_path and os.path.isdir(dir_path):
                shutil.rmtree(dir_path, ignore_errors=True)
    except Exception as e:
        logger.warning("Failed to prune projects: %s", e)
