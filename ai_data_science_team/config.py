from dataclasses import dataclass, field, asdict
from typing import Any, Optional, Callable

from langgraph.types import Checkpointer


@dataclass
class AgentConfig:
    model: Any
    n_samples: int = 30
    log: bool = False
    log_path: Optional[str] = None
    file_name: str = "agent.py"
    function_name: str = "agent_function"
    overwrite: bool = True
    human_in_the_loop: bool = False
    bypass_recommended_steps: bool = False
    bypass_explain_code: bool = False
    checkpointer: Optional[Checkpointer] = None
    
    def to_params(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    def with_overrides(self, **kwargs) -> "AgentConfig":
        params = asdict(self)
        params.update(kwargs)
        return AgentConfig(**params)


@dataclass
class MLAgentConfig(AgentConfig):
    model_directory: Optional[str] = None
    enable_mlflow: bool = False
    mlflow_tracking_uri: Optional[str] = None
    mlflow_artifact_root: Optional[str] = None
    mlflow_experiment_name: str = "ML Experiment"
    mlflow_run_name: Optional[str] = None


@dataclass
class H2OAgentConfig(MLAgentConfig):
    mlflow_experiment_name: str = "H2O AutoML"


@dataclass
class SQLAgentConfig(AgentConfig):
    sql_url: Optional[str] = None
    smart_schema_pruning: bool = True


@dataclass
class CodingAgentGraphConfig:
    human_in_the_loop: bool = False
    bypass_recommended_steps: bool = False
    bypass_explain_code: bool = False
    checkpointer: Optional[Callable] = None
    agent_name: str = "coding_agent"
    human_review_node_name: str = "human_review"
    max_retries_key: str = "max_retries"
    retry_count_key: str = "retry_count"
    
    def to_params(self) -> dict:
        return asdict(self)


@dataclass
class NodeNames:
    recommended: str
    create: str
    execute: str
    fix: str
    explain: str
