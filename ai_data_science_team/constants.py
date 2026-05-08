from enum import Enum
from dataclasses import dataclass
from typing import ClassVar


class SessionKeys(str, Enum):
    UNDO_STACK = "pipeline_studio_undo_stack"
    REDO_STACK = "pipeline_studio_redo_stack"
    TEAM_STATE = "team_state"
    ARTIFACTS = "pipeline_studio_artifacts"
    NODE_ID_PENDING = "pipeline_studio_node_id_pending"
    AUTOFOLLOW_PENDING = "pipeline_studio_autofollow_pending"
    HISTORY_NOTICE = "pipeline_studio_history_notice"
    PROJECT_NOTICE = "pipeline_studio_project_notice"
    CODE_DRAFTS_STORE = "pipeline_studio_code_drafts_store"
    CODE_DRAFTS_LOADED = "_pipeline_studio_code_drafts_store_loaded"
    ARTIFACT_STORE_LOADED = "_pipeline_studio_artifact_store_loaded"
    FLOW_LAYOUT_LOADED = "_pipeline_studio_flow_layout_loaded"
    REGISTRY_LOADED = "_pipeline_studio_registry_loaded"
    DATASET_STORE_LOADED = "_pipeline_studio_dataset_store_loaded"
    ACTIVE_DATASET_OVERRIDE_PENDING = "active_dataset_id_override_pending"
    SQL_URL_SYNC_FLAG = "_sync_sql_url_input"
    ACTIVE_DATASET_OVERRIDE_SYNC_FLAG = "_sync_active_dataset_override"


class ArtifactGroups(str, Enum):
    CHART = "Chart"
    EDA = "EDA"
    MODEL = "Model"
    MLFLOW = "MLflow"


@dataclass(frozen=True)
class ArtifactKeys:
    CHART_KEYS: ClassVar[tuple] = ("plotly_graph", "viz_error", "viz_warning")
    EDA_KEYS: ClassVar[tuple] = ("eda_reports",)
    MODEL_KEYS: ClassVar[tuple] = ("model_info", "eval_artifacts", "eval_plotly_graph")
    MLFLOW_KEYS: ClassVar[tuple] = ("mlflow_artifacts",)
    
    @classmethod
    def all_keys(cls) -> list[str]:
        return sorted(
            set(cls.CHART_KEYS) | set(cls.EDA_KEYS) | set(cls.MODEL_KEYS) | set(cls.MLFLOW_KEYS)
        )


@dataclass(frozen=True)
class PipelineStudioLimits:
    ARTIFACT_STORE_MAX_ITEMS: ClassVar[int] = 250
    FLOW_LAYOUT_MAX_ITEMS: ClassVar[int] = 100
    REGISTRY_MAX_ITEMS: ClassVar[int] = 50
    CODE_DRAFTS_MAX_ITEMS: ClassVar[int] = 250
    DATASET_STORE_MAX_ITEMS: ClassVar[int] = 0
    DATASET_CACHE_MAX_ITEMS_DEFAULT: ClassVar[int] = 5
    DATASET_CACHE_MAX_MB_DEFAULT: ClassVar[int] = 500
    PROJECT_PREVIEW_MAX_ROWS: ClassVar[int] = 20
    PROJECT_PREVIEW_MAX_COLS: ClassVar[int] = 50
    SCHEMA_PREVIEW_MAX_COLS: ClassVar[int] = 200
    FINGERPRINT_SAMPLE_MAX_ROWS: ClassVar[int] = 2_000
    TRANSFORM_CODE_MAX_CHARS: ClassVar[int] = 12_000
    TRANSFORM_SNIPPET_MAX_CHARS: ClassVar[int] = 6_000
    LIVE_LOG_BUFFER_MAX_CHARS: ClassVar[int] = 50_000
    LIVE_LOG_JOIN_TIMEOUT_SEC: ClassVar[float] = 0.1
    PROFILE_SAMPLE_MAX_ROWS: ClassVar[int] = 5_000
    PROFILE_SAMPLE_MAX_COLS: ClassVar[int] = 200
    UI_PREVIEW_MAX_ROWS: ClassVar[int] = 200
    PROJECTS_MAX_ITEMS: ClassVar[int] = 25
    HISTORY_MAX_ITEMS: ClassVar[int] = 25


ARTIFACT_GROUP_MAPPING: dict[str, tuple[str, ...]] = {
    ArtifactGroups.CHART.value: ArtifactKeys.CHART_KEYS,
    ArtifactGroups.EDA.value: ArtifactKeys.EDA_KEYS,
    ArtifactGroups.MODEL.value: ArtifactKeys.MODEL_KEYS,
    ArtifactGroups.MLFLOW.value: ArtifactKeys.MLFLOW_KEYS,
}
