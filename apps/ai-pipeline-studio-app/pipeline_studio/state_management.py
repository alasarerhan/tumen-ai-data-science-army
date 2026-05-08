import streamlit as st
from typing import Any, Optional, Dict, List
from dataclasses import dataclass, field

from ai_data_science_team.constants import SessionKeys


@dataclass
class PipelineStudioState:
    _session_state: Dict[str, Any] = field(default_factory=dict)
    
    def __init__(self, session_state: Optional[Dict[str, Any]] = None):
        self._session_state = session_state if session_state is not None else st.session_state
    
    def _get(self, key: str, default: Any = None) -> Any:
        return self._session_state.get(key, default)
    
    def _set(self, key: str, value: Any) -> None:
        self._session_state[key] = value
    
    @property
    def undo_stack(self) -> List[dict]:
        return self._get(SessionKeys.UNDO_STACK, [])
    
    @undo_stack.setter
    def undo_stack(self, value: List[dict]) -> None:
        self._set(SessionKeys.UNDO_STACK, value)
    
    @property
    def redo_stack(self) -> List[dict]:
        return self._get(SessionKeys.REDO_STACK, [])
    
    @redo_stack.setter
    def redo_stack(self, value: List[dict]) -> None:
        self._set(SessionKeys.REDO_STACK, value)
    
    @property
    def team_state(self) -> Dict[str, Any]:
        return self._get(SessionKeys.TEAM_STATE, {})
    
    @team_state.setter
    def team_state(self, value: Dict[str, Any]) -> None:
        self._set(SessionKeys.TEAM_STATE, value)
    
    @property
    def artifacts(self) -> Dict[str, Any]:
        return self._get(SessionKeys.ARTIFACTS, {})
    
    @artifacts.setter
    def artifacts(self, value: Dict[str, Any]) -> None:
        self._set(SessionKeys.ARTIFACTS, value)
    
    @property
    def node_id_pending(self) -> Optional[str]:
        return self._get(SessionKeys.NODE_ID_PENDING)
    
    @node_id_pending.setter
    def node_id_pending(self, value: Optional[str]) -> None:
        self._set(SessionKeys.NODE_ID_PENDING, value)
    
    @property
    def autofollow_pending(self) -> bool:
        return self._get(SessionKeys.AUTOFOLLOW_PENDING, False)
    
    @autofollow_pending.setter
    def autofollow_pending(self, value: bool) -> None:
        self._set(SessionKeys.AUTOFOLLOW_PENDING, value)
    
    @property
    def history_notice(self) -> Optional[str]:
        return self._get(SessionKeys.HISTORY_NOTICE)
    
    @history_notice.setter
    def history_notice(self, value: Optional[str]) -> None:
        self._set(SessionKeys.HISTORY_NOTICE, value)
    
    @property
    def project_notice(self) -> Optional[str]:
        return self._get(SessionKeys.PROJECT_NOTICE)
    
    @project_notice.setter
    def project_notice(self, value: Optional[str]) -> None:
        self._set(SessionKeys.PROJECT_NOTICE, value)
    
    @property
    def datasets(self) -> Dict[str, Any]:
        team = self.team_state
        return team.get("datasets", {}) if isinstance(team, dict) else {}
    
    @property
    def active_dataset_id(self) -> Optional[str]:
        team = self.team_state
        return team.get("active_dataset_id") if isinstance(team, dict) else None
    
    def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        return self.datasets.get(dataset_id)
    
    def set_active_dataset(self, dataset_id: str) -> None:
        team = dict(self.team_state)
        team["active_dataset_id"] = dataset_id
        self.team_state = team
    
    def clear_notice(self) -> None:
        self.history_notice = None
        self.project_notice = None


def get_state() -> PipelineStudioState:
    return PipelineStudioState(st.session_state)


def init_state() -> None:
    state = get_state()
    if not state.undo_stack:
        state.undo_stack = []
    if not state.redo_stack:
        state.redo_stack = []
