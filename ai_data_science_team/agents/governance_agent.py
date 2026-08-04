from __future__ import annotations

"""J7 Agent.

Phase-5 agent wrapper for spec J7.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.governance``) with
LangChain ``@tool`` decorators and exposes the standard
``make_governance_agent`` factory + ``J7Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``governance.evaluate``
"""

import logging  # noqa: E402, F401
from typing import (  # noqa: E402
    Any,  # noqa: E402, F401
    Dict,
    Optional,
    Tuple,
)

from langchain.tools import tool  # noqa: E402, F401
from langchain_core.messages import AIMessage, BaseMessage  # noqa: E402, F401
from langgraph.graph import END, START, StateGraph  # noqa: E402, F401
from langgraph.graph.message import add_messages  # noqa: E402, F401
from langgraph.types import Checkpointer  # noqa: E402, F401
from typing_extensions import Annotated, Sequence, TypedDict  # noqa: E402, F401

from ai_data_science_team.templates import BaseAgent  # noqa: E402, F401
from ai_data_science_team.tools.governance import (  # noqa: E402, F401
    ApprovalChain,
    AuditLog,
    RiskPolicy,
    approve_step,
    assign_risk,
    build_checklist,
    chain_progress,
    evaluate_checklist,
    promotion_gate,
    render_audit_report,
    required_approvers,
    start_approval_chain,
)
from ai_data_science_team.utils.regex import format_agent_name  # noqa: E402, F401

logger = logging.getLogger(__name__)

AGENT_NAME = "governance_agent"
NODE_TYPE = "governance.evaluate"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------


@tool(response_format="content_and_artifact")
def assign_risk_wrapped() -> Tuple[str, dict]:
    """Tool wrapper for ``assign_risk``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j7_assign_risk")
    kwargs = {}
    try:
        result = assign_risk(**kwargs)
    except Exception as exc:
        return f"Tool j7_assign_risk failed: {exc}", {
            "assign_risk": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j7_assign_risk: ok"
    return content, {
        "assign_risk": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def required_approvers_wrapped(risk_class: str, policy: RiskPolicy) -> Tuple[str, dict]:
    """Tool wrapper for ``required_approvers``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j7_required_approvers")
    kwargs = {"risk_class": risk_class, "policy": policy}
    try:
        result = required_approvers(**kwargs)
    except Exception as exc:
        return f"Tool j7_required_approvers failed: {exc}", {
            "required_approvers": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j7_required_approvers: ok"
    return content, {
        "required_approvers": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def start_approval_chain_wrapped() -> Tuple[str, dict]:
    """Tool wrapper for ``start_approval_chain``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j7_start_approval_chain")
    kwargs = {}
    try:
        result = start_approval_chain(**kwargs)
    except Exception as exc:
        return f"Tool j7_start_approval_chain failed: {exc}", {
            "start_approval_chain": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j7_start_approval_chain: ok"
    return content, {
        "start_approval_chain": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def approve_step_wrapped(chain: ApprovalChain) -> Tuple[str, dict]:
    """Tool wrapper for ``approve_step``.

    Approve a step. Enforces: (1) step must exist, (2) role

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j7_approve_step")
    kwargs = {"chain": chain}
    try:
        result = approve_step(**kwargs)
    except Exception as exc:
        return f"Tool j7_approve_step failed: {exc}", {
            "approve_step": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j7_approve_step: ok"
    return content, {
        "approve_step": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def chain_progress_wrapped(chain: ApprovalChain) -> Tuple[str, dict]:
    """Tool wrapper for ``chain_progress``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j7_chain_progress")
    kwargs = {"chain": chain}
    try:
        result = chain_progress(**kwargs)
    except Exception as exc:
        return f"Tool j7_chain_progress failed: {exc}", {
            "chain_progress": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j7_chain_progress: ok"
    return content, {
        "chain_progress": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def build_checklist_wrapped() -> Tuple[str, dict]:
    """Tool wrapper for ``build_checklist``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j7_build_checklist")
    kwargs = {}
    try:
        result = build_checklist(**kwargs)
    except Exception as exc:
        return f"Tool j7_build_checklist failed: {exc}", {
            "build_checklist": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j7_build_checklist: ok"
    return content, {
        "build_checklist": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def evaluate_checklist_wrapped() -> Tuple[str, dict]:
    """Tool wrapper for ``evaluate_checklist``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j7_evaluate_checklist")
    kwargs = {}
    try:
        result = evaluate_checklist(**kwargs)
    except Exception as exc:
        return f"Tool j7_evaluate_checklist failed: {exc}", {
            "evaluate_checklist": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j7_evaluate_checklist: ok"
    return content, {
        "evaluate_checklist": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def render_audit_report_wrapped(log: AuditLog) -> Tuple[str, dict]:
    """Tool wrapper for ``render_audit_report``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j7_render_audit_report")
    kwargs = {"log": log}
    try:
        result = render_audit_report(**kwargs)
    except Exception as exc:
        return f"Tool j7_render_audit_report failed: {exc}", {
            "render_audit_report": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j7_render_audit_report: ok"
    return content, {
        "render_audit_report": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def promotion_gate_wrapped() -> Tuple[str, dict]:
    """Tool wrapper for ``promotion_gate``.

    Return whether promotion to prod is allowed, with reasons.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j7_promotion_gate")
    kwargs = {}
    try:
        result = promotion_gate(**kwargs)
    except Exception as exc:
        return f"Tool j7_promotion_gate failed: {exc}", {
            "promotion_gate": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j7_promotion_gate: ok"
    return content, {
        "promotion_gate": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


GOVERNANCE_TOOLS = [
    assign_risk_wrapped,
    required_approvers_wrapped,
    start_approval_chain_wrapped,
    approve_step_wrapped,
    chain_progress_wrapped,
    build_checklist_wrapped,
    evaluate_checklist_wrapped,
    render_audit_report_wrapped,
    promotion_gate_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_governance_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the J7 agent."""
    if create_react_agent_kwargs is None:
        create_react_agent_kwargs = {}
    if invoke_react_agent_kwargs is None:
        invoke_react_agent_kwargs = {}

    from langchain.agents import create_agent  # noqa: E402, F401

    class GraphState(TypedDict):
        messages: Annotated[Sequence[BaseMessage], add_messages]
        user_instructions: str
        tool_calls: list

    react_agent = create_agent(
        model,
        tools=GOVERNANCE_TOOLS,
        state_schema=GraphState,
        checkpointer=checkpointer,
        **create_react_agent_kwargs,
    )

    def prepare_messages(state: GraphState):
        logger.info(format_agent_name(AGENT_NAME))
        logger.info("    * PREPARE MESSAGES")
        if state.get("messages"):
            return {}
        return {"messages": [("user", state.get("user_instructions"))]}

    def run_react_agent(state: GraphState):
        logger.info("    * RUN REACT AGENT FOR J7")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [
            (
                "system",
                "You are the J7 agent. Use the available tools to complete the user's request.",
            )
        ] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING J7 RESULTS")
        internal = state.get("messages", []) or []
        if not internal:
            return {"messages": [], "tool_calls": []}
        last_ai = None
        for msg in reversed(internal):
            role = getattr(msg, "role", None) or getattr(msg, "type", None)
            if role in ("assistant", "ai"):
                last_ai = AIMessage(content=getattr(msg, "content", ""), name=AGENT_NAME)
                break
        if last_ai is None:
            last_ai = AIMessage(content=getattr(internal[-1], "content", ""), name=AGENT_NAME)
        tool_calls = []
        for msg in internal:
            name = getattr(getattr(msg, "tool_call_id", None), "name", None) or getattr(
                msg, "name", None
            )
            if name:
                tool_calls.append(name)
        if log_tool_calls and tool_calls:
            for tc in tool_calls:
                logger.info(f"    * Tool: {tc}")
        return {
            "messages": [last_ai],
            "internal_messages": internal,
            "tool_calls": tool_calls,
        }

    workflow = StateGraph(GraphState)
    workflow.add_node("prepare_messages", prepare_messages)
    workflow.add_node("react_agent", react_agent)
    workflow.add_node("post_process", post_process)
    workflow.add_edge(START, "prepare_messages")
    workflow.add_edge("prepare_messages", "react_agent")
    workflow.add_edge("react_agent", "post_process")
    workflow.add_edge("post_process", END)
    return workflow.compile(checkpointer=checkpointer, name=AGENT_NAME)


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------


class GovernanceAgent(BaseAgent):
    """OO wrapper for the J7 agent (node type ``governance.evaluate``)."""

    def __init__(
        self,
        model: Any,
        checkpointer: Optional[Checkpointer] = None,
        create_react_agent_kwargs: Optional[Dict] = None,
        invoke_react_agent_kwargs: Optional[Dict] = None,
        log_tool_calls: bool = True,
    ):
        self._params = {
            "model": model,
            "checkpointer": checkpointer,
            "create_react_agent_kwargs": create_react_agent_kwargs or {},
            "invoke_react_agent_kwargs": invoke_react_agent_kwargs or {},
            "log_tool_calls": log_tool_calls,
        }
        self._compiled_graph = self._make_compiled_graph()
        self.response = None

    def _make_compiled_graph(self):
        self.response = None
        return make_governance_agent(**self._params)

    def update_params(self, **kwargs):
        for k, v in kwargs.items():
            self._params[k] = v
        self._compiled_graph = self._make_compiled_graph()

    def invoke_agent(self, user_instructions: str, **kwargs):
        self.response = self._compiled_graph.invoke(
            {"messages": [("user", user_instructions)]}, **kwargs
        )
        return None

    def get_ai_message(self, markdown: bool = False):
        if not self.response or "messages" not in self.response:
            return None
        from IPython.display import Markdown as _Markdown  # noqa: E402, F401

        for msg in reversed(self.response.get("messages", [])):
            content = getattr(msg, "content", "")
            if content:
                return _Markdown(content) if markdown else content
        return None

    def get_tool_calls(self):
        if not self.response:
            return None
        return self.response.get("tool_calls")


__all__ = [
    "AGENT_NAME",
    "NODE_TYPE",
    "GovernanceAgent",
    "make_governance_agent",
    "GOVERNANCE_TOOLS",
]
