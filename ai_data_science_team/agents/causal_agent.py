from __future__ import annotations

"""A5 Agent.

Phase-5 agent wrapper for spec A5.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.causal``) with
LangChain ``@tool`` decorators and exposes the standard
``make_causal_agent`` factory + ``A5Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``model.causal_infer``
"""

from typing import (Dict, Optional, Tuple)  # noqa: E402
import logging  # noqa: E402, F401
from typing import Any  # noqa: E402, F401

from langchain.tools import tool  # noqa: E402, F401
from langchain_core.messages import AIMessage, BaseMessage  # noqa: E402, F401
from langgraph.graph import END, START, StateGraph  # noqa: E402, F401
from langgraph.graph.message import add_messages  # noqa: E402, F401
from langgraph.types import Checkpointer  # noqa: E402, F401
from typing_extensions import Annotated, Sequence, TypedDict  # noqa: E402, F401

from ai_data_science_team.templates import BaseAgent  # noqa: E402, F401
from ai_data_science_team.utils.regex import format_agent_name  # noqa: E402, F401



from ai_data_science_team.tools.causal import (  # noqa: E402, F401
    adj_lift,
    check_propensity_overlap,
    did_lift,
    e_value,
)


logger = logging.getLogger(__name__)

AGENT_NAME = "causal_agent"
NODE_TYPE = "model.causal_infer"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def did_lift_wrapped(pre_treat_y_pre: Sequence[float], pre_treat_y_post: Sequence[float], control_y_pre: Sequence[float], control_y_post: Sequence[float]) -> Tuple[str, dict]:
    """Tool wrapper for ``did_lift``.

    Diff-in-diff average treatment effect on the treated.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: a5_did_lift")
    kwargs = {'pre_treat_y_pre': pre_treat_y_pre, 'pre_treat_y_post': pre_treat_y_post, 'control_y_pre': control_y_pre, 'control_y_post': control_y_post}
    try:
        result = did_lift(**kwargs)
    except Exception as exc:
        return f"Tool a5_did_lift failed: {exc}", {
            "did_lift": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "a5_did_lift: ok"
    return content, {
        "did_lift": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def adj_lift_wrapped(y: Sequence[float], treatment: Sequence[int], covariates: Sequence[Sequence[float]]) -> Tuple[str, dict]:
    """Tool wrapper for ``adj_lift``.

    Adjusted mean difference with one-hot treatment assignment.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: a5_adj_lift")
    kwargs = {'y': y, 'treatment': treatment, 'covariates': covariates}
    try:
        result = adj_lift(**kwargs)
    except Exception as exc:
        return f"Tool a5_adj_lift failed: {exc}", {
            "adj_lift": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "a5_adj_lift: ok"
    return content, {
        "adj_lift": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def check_propensity_overlap_wrapped(propensity: Sequence[float], label: str) -> Tuple[str, dict]:
    """Tool wrapper for ``check_propensity_overlap``.

    Sanity check on the propensity-score support.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: a5_check_propensity_overlap")
    kwargs = {'propensity': propensity, 'label': label}
    try:
        result = check_propensity_overlap(**kwargs)
    except Exception as exc:
        return f"Tool a5_check_propensity_overlap failed: {exc}", {
            "check_propensity_overlap": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "a5_check_propensity_overlap: ok"
    return content, {
        "check_propensity_overlap": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def e_value_wrapped(point_estimate: float) -> Tuple[str, dict]:
    """Tool wrapper for ``e_value``.

    E-value sensitivity bound (Vansteelandt 2017).

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: a5_e_value")
    kwargs = {'point_estimate': point_estimate}
    try:
        result = e_value(**kwargs)
    except Exception as exc:
        return f"Tool a5_e_value failed: {exc}", {
            "e_value": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "a5_e_value: ok"
    return content, {
        "e_value": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


CAUSAL_INFERENCE_TOOLS = [
    did_lift_wrapped,
    adj_lift_wrapped,
    check_propensity_overlap_wrapped,
    e_value_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_causal_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the A5 agent."""
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
        tools=CAUSAL_INFERENCE_TOOLS,
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
        logger.info("    * RUN REACT AGENT FOR A5")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [("system", "You are the A5 agent. Use the available tools to complete the user's request.")] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING A5 RESULTS")
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
            name = getattr(getattr(msg, "tool_call_id", None), "name", None) or getattr(msg, "name", None)
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


class CausalInferenceAgent(BaseAgent):
    """OO wrapper for the A5 agent (node type ``model.causal_infer``)."""

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
        return make_causal_agent(**self._params)

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
    "CausalInferenceAgent",
    "make_causal_agent",
    "CAUSAL_INFERENCE_TOOLS",
]
