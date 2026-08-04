from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ai_data_science_team.constants import PipelineStudioLimits

if TYPE_CHECKING:
    PipelineStudioState = object  # type: ignore[assignment,misc]


class HistoryManager:
    def __init__(self, state: "PipelineStudioState"):
        self._state = state

    def push(self, action: dict) -> None:
        try:
            self._init_stacks()
            undo = list(self._state.undo_stack)
            undo.append(action if isinstance(action, dict) else {})
            max_items = PipelineStudioLimits.HISTORY_MAX_ITEMS
            if len(undo) > max_items:
                undo = undo[-max_items:]
            self._state.undo_stack = undo
            self._state.redo_stack = []
        except Exception:
            pass

    def pop_undo(self) -> Optional[dict]:
        self._init_stacks()
        undo = list(self._state.undo_stack)
        if not undo:
            return None
        action = undo.pop()
        self._state.undo_stack = undo
        return action if isinstance(action, dict) else {}

    def push_redo(self, action: dict) -> None:
        try:
            redo = list(self._state.redo_stack)
            redo.append(action if isinstance(action, dict) else {})
            self._state.redo_stack = redo
        except Exception:
            pass

    def pop_redo(self) -> Optional[dict]:
        redo = list(self._state.redo_stack)
        if not redo:
            return None
        action = redo.pop()
        self._state.redo_stack = redo
        return action if isinstance(action, dict) else {}

    def can_undo(self) -> bool:
        return len(self._state.undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self._state.redo_stack) > 0

    def _init_stacks(self) -> None:
        if not self._state.undo_stack:
            self._state.undo_stack = []
        if not self._state.redo_stack:
            self._state.redo_stack = []


def _extract_snapshot(action: dict, phase: str) -> Optional[dict]:
    if not isinstance(action, dict):
        return None

    direct_keys = {
        "team_state": action.get(f"team_state_{phase}"),
        "artifacts": action.get(f"artifacts_{phase}"),
        "node_id_pending": action.get(f"node_id_pending_{phase}"),
        "autofollow_pending": action.get(f"autofollow_pending_{phase}"),
        "active_dataset_id": action.get(f"active_dataset_id_{phase}"),
        "history_notice": action.get(f"history_notice_{phase}"),
    }
    if any(value is not None for value in direct_keys.values()):
        return direct_keys

    nested = action.get(f"snapshot_{phase}")
    return nested if isinstance(nested, dict) else None


def _apply_snapshot(state: "PipelineStudioState", snapshot: dict) -> None:
    if not isinstance(snapshot, dict):
        return

    team_state = snapshot.get("team_state")
    if isinstance(team_state, dict):
        state.team_state = dict(team_state)

    artifacts = snapshot.get("artifacts")
    if isinstance(artifacts, dict):
        state.artifacts = dict(artifacts)

    if "active_dataset_id" in snapshot:
        active_dataset_id = snapshot.get("active_dataset_id")
        if isinstance(active_dataset_id, str) and active_dataset_id:
            state.set_active_dataset(active_dataset_id)

    if "node_id_pending" in snapshot:
        node_id_pending = snapshot.get("node_id_pending")
        state.node_id_pending = node_id_pending if isinstance(node_id_pending, str) else None

    if "autofollow_pending" in snapshot:
        state.autofollow_pending = bool(snapshot.get("autofollow_pending"))

    if "history_notice" in snapshot:
        history_notice = snapshot.get("history_notice")
        state.history_notice = history_notice if isinstance(history_notice, str) else None


def _apply_snapshot_action(
    *,
    state: "PipelineStudioState",
    action: dict,
    phase: str,
    verb: str,
) -> bool:
    snapshot = _extract_snapshot(action, phase)
    if not snapshot:
        return False

    _apply_snapshot(state, snapshot)
    action_type = str(action.get("type") or "state_change")
    state.history_notice = f"{verb} action: `{action_type}`."
    return True


def undo_last_action(state: "PipelineStudioState") -> None:
    manager = HistoryManager(state)

    action = manager.pop_undo()
    if not action:
        return

    action_type = str(action.get("type") or "")
    if _apply_snapshot_action(state=state, action=action, phase="before", verb="Undid"):
        manager.push_redo(action)
        return

    if action_type not in {"create_dataset", "create_datasets"}:
        state.history_notice = f"Undo not implemented for action type `{action_type}`."
        manager.push_redo(action)
        return

    prev_active = action.get("prev_active_dataset_id")
    prev_active = prev_active if isinstance(prev_active, str) and prev_active else None

    remove_ids: List[str] = []
    if action_type == "create_dataset":
        dataset_id = action.get("dataset_id")
        if isinstance(dataset_id, str) and dataset_id:
            remove_ids = [dataset_id]
    else:
        ids = action.get("dataset_ids")
        ids = ids if isinstance(ids, list) else []
        remove_ids = [str(x) for x in ids if isinstance(x, str) and x]

    if not remove_ids:
        state.history_notice = "Undo failed: missing dataset id(s)."
        return

    datasets = state.datasets
    remove_set = set(remove_ids)
    existing_to_remove = [did for did in remove_ids if did in datasets]

    if not existing_to_remove:
        state.history_notice = (
            f"Undo skipped: dataset(s) already gone: {', '.join([f'`{x}`' for x in remove_ids])}."
        )
        return

    for did, ent in datasets.items():
        if did in remove_set or not isinstance(ent, dict):
            continue
        pids = ent.get("parent_ids")
        pids = pids if isinstance(pids, list) else []
        pid = ent.get("parent_id")
        parents = []
        if isinstance(pid, str) and pid:
            parents.append(pid)
        parents.extend([p for p in pids if isinstance(p, str) and p])
        if any(p in remove_set for p in parents):
            state.history_notice = f"Cannot undo: dataset(s) have downstream dataset `{did}`."
            manager.push_redo(action)
            return

    new_datasets = {k: v for k, v in datasets.items() if k not in remove_set}
    team = dict(state.team_state)
    team["datasets"] = new_datasets

    active_now = state.active_dataset_id
    if prev_active and prev_active in new_datasets:
        team["active_dataset_id"] = prev_active
    elif active_now in remove_set or (active_now and active_now not in new_datasets):
        best_id = _pick_newest_dataset(new_datasets)
        team["active_dataset_id"] = best_id

    state.team_state = team
    manager.push_redo(action)
    state.history_notice = f"Undid last action: removed {len(existing_to_remove)} dataset(s)."


def redo_last_action(state: "PipelineStudioState") -> None:
    manager = HistoryManager(state)

    action = manager.pop_redo()
    if not action:
        return

    action_type = str(action.get("type") or "")
    if _apply_snapshot_action(state=state, action=action, phase="after", verb="Redid"):
        manager.push(action)
        return

    if action_type not in {"create_dataset", "create_datasets"}:
        state.history_notice = f"Redo not implemented for action type `{action_type}`."
        manager.push_redo(action)
        return

    dataset_ids: List[str] = []
    entries_by_id: Dict[str, dict] = {}

    if action_type == "create_dataset":
        dataset_id = action.get("dataset_id")
        dataset_entry = action.get("dataset_entry")
        if isinstance(dataset_id, str) and dataset_id and isinstance(dataset_entry, dict):
            dataset_ids = [dataset_id]
            entries_by_id = {dataset_id: dataset_entry}
    else:
        ids = action.get("dataset_ids")
        ids = ids if isinstance(ids, list) else []
        dataset_ids = [str(x) for x in ids if isinstance(x, str) and x]
        eby = action.get("dataset_entries_by_id")
        eby = eby if isinstance(eby, dict) else {}
        entries_by_id = {
            str(k): v for k, v in eby.items() if isinstance(k, str) and isinstance(v, dict)
        }

    if not dataset_ids or any(did not in entries_by_id for did in dataset_ids):
        state.history_notice = "Redo failed: missing dataset payload."
        return

    datasets = dict(state.datasets)
    for did in dataset_ids:
        datasets[did] = entries_by_id[did]

    team = dict(state.team_state)
    team["datasets"] = datasets
    team["active_dataset_id"] = dataset_ids[-1]
    state.team_state = team

    state.node_id_pending = dataset_ids[-1]
    state.autofollow_pending = True
    state.history_notice = f"Redid last action: restored {len(dataset_ids)} dataset(s)."

    manager.push(action)


def _pick_newest_dataset(datasets: Dict[str, Any]) -> Optional[str]:
    best_id = None
    best_ts = -1.0
    for did, ent in datasets.items():
        if not isinstance(ent, dict):
            continue
        try:
            ts = float(ent.get("created_ts") or 0.0)
        except Exception:
            ts = 0.0
        if ts >= best_ts:
            best_ts = ts
            best_id = did
    return best_id
