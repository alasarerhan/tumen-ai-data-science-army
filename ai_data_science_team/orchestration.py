# BUSINESS SCIENCE UNIVERSITY
# AI DATA SCIENCE TEAM
# ***
# Orchestration facade — M22
# ai_data_science_team/orchestration.py
#
# This module re-exports all public M22 orchestration primitives so that
# callers can use a single import path:
#
#   from ai_data_science_team.orchestration import (
#       AgentRegistry, ContextStore, WorkflowResolver,
#       RuntimeEngine, WorkflowSignal, SignalStore, OrchestratorAgent,
#   )

from ai_data_science_team.agent_registry import AgentRegistry, AgentMetadata
from ai_data_science_team.context_store import ContextStore
from ai_data_science_team.workflow_resolver import (
    WorkflowResolver,
    validate_spec,
    build_step,
    build_spec,
)
from ai_data_science_team.runtime_engine import RuntimeEngine, RunResult, StepResult
from ai_data_science_team.signals import (
    WorkflowSignal,
    SignalStore,
    SignalType,
    get_signal_store,
)
from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent

__all__ = [
    # Registry
    "AgentRegistry",
    "AgentMetadata",
    # Context
    "ContextStore",
    # Resolver
    "WorkflowResolver",
    "validate_spec",
    "build_step",
    "build_spec",
    # Engine
    "RuntimeEngine",
    "RunResult",
    "StepResult",
    # Signals
    "WorkflowSignal",
    "SignalStore",
    "SignalType",
    "get_signal_store",
    # Agent
    "OrchestratorAgent",
]
