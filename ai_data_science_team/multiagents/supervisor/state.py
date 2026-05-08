from typing import Sequence, TypedDict, Annotated, Optional, Dict, Any, List

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


TEAM_MAX_MESSAGES = 20
TEAM_MAX_MESSAGE_CHARS = 2000


def _is_agent_output_report_message(m: BaseMessage) -> bool:
    """
    Detect verbose JSON "Agent Outputs" reports emitted by node_func_report_agent_outputs.
    """
    from langchain_core.messages import AIMessage
    
    if not isinstance(m, AIMessage):
        return False
    content = getattr(m, "content", None)
    if not isinstance(content, str) or not content:
        return False
    s = content.lstrip()
    if not s.startswith("{"):
        return False
    head = s[:1200]
    return '"report_title"' in head and (
        "Agent Outputs" in head or "Agent Output Summary" in head
    )


def _supervisor_merge_messages(
    left: Sequence[BaseMessage] | None,
    right: Sequence[BaseMessage] | None,
) -> List[BaseMessage]:
    """
    Merge conversation messages safely:
    - Use LangGraph's ID-aware add_messages reducer
    - Drop tool/function role messages
    - Strip tool_calls payloads from AI messages
    - Truncate very long message bodies
    - Keep only the last N messages
    """
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    
    merged = add_messages(left or [], right or [])

    cleaned: list[BaseMessage] = []
    for m in merged:
        role = getattr(m, "type", None) or getattr(m, "role", None)
        if role in ("tool", "function"):
            continue
        if _is_agent_output_report_message(m):
            continue

        content = getattr(m, "content", "")
        message_id = getattr(m, "id", None)

        if isinstance(content, str) and len(content) > TEAM_MAX_MESSAGE_CHARS:
            content = content[:TEAM_MAX_MESSAGE_CHARS] + "\n...[truncated]..."

        if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
            cleaned.append(
                AIMessage(
                    content=content or "",
                    name=getattr(m, "name", None),
                    id=message_id,
                )
            )
            continue

        if isinstance(m, AIMessage):
            cleaned.append(
                AIMessage(
                    content=content or "",
                    name=getattr(m, "name", None),
                    id=message_id,
                )
            )
        elif isinstance(m, HumanMessage):
            cleaned.append(HumanMessage(content=content or "", id=message_id))
        elif isinstance(m, SystemMessage):
            cleaned.append(SystemMessage(content=content or "", id=message_id))
        else:
            cleaned.append(m)

    return cleaned[-TEAM_MAX_MESSAGES:]


def _clean_messages(msgs: Sequence[BaseMessage]) -> Sequence[BaseMessage]:
    """
    Strip tool call payloads to avoid OpenAI 'tool_calls' vs 'functions' conflicts.
    """
    from langchain_core.messages import AIMessage
    
    cleaned: list[BaseMessage] = []
    for m in msgs or []:
        role = getattr(m, "type", None) or getattr(m, "role", None)
        if role in ("tool", "function"):
            continue
        if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
            cleaned.append(
                AIMessage(
                    content=getattr(m, "content", "") or "",
                    name=getattr(m, "name", None),
                    id=getattr(m, "id", None),
                )
            )
        else:
            cleaned.append(m)
    return cleaned


class SupervisorDSState(TypedDict):
    """
    Shared state for the supervisor-led data science team.
    """

    messages: Annotated[Sequence[BaseMessage], _supervisor_merge_messages]
    next: str
    last_worker: Optional[str]
    active_data_key: Optional[str]
    active_dataset_id: Optional[str]
    datasets: Dict[str, Any]
    handled_request_id: Optional[str]
    handled_steps: Dict[str, bool]
    attempted_steps: Dict[str, bool]
    workflow_plan_request_id: Optional[str]
    workflow_plan: Optional[dict]
    target_variable: Optional[str]

    data_raw: Optional[dict]
    data_sql: Optional[dict]
    data_wrangled: Optional[dict]
    data_cleaned: Optional[dict]
    eda_artifacts: Optional[dict]
    viz_graph: Optional[dict]
    feature_data: Optional[dict]
    model_info: Optional[dict]
    eval_artifacts: Optional[dict]
    mlflow_artifacts: Optional[dict]
    artifacts: Dict[str, Any]
