from __future__ import annotations

"""A3 Agent.

Phase-5 agent wrapper for spec A3.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.bayesian``) with
LangChain ``@tool`` decorators and exposes the standard
``make_bayesian_agent`` factory + ``A3Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``model.bayesian_update``
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



from ai_data_science_team.tools.bayesian import (  # noqa: E402, F401
    BetaPosterior,
    bayes_decision,
    beta_posterior,
    normal_means_posterior,
)


logger = logging.getLogger(__name__)

AGENT_NAME = "bayesian_agent"
NODE_TYPE = "model.bayesian_update"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def beta_posterior_wrapped(successes: int, failures: int) -> Tuple[str, dict]:
    """Tool wrapper for ``beta_posterior``.

    Compute the Beta-Binomial posterior parameters.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: a3_beta_posterior")
    kwargs = {'successes': successes, 'failures': failures}
    try:
        result = beta_posterior(**kwargs)
    except Exception as exc:
        return f"Tool a3_beta_posterior failed: {exc}", {
            "beta_posterior": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "a3_beta_posterior: ok"
    return content, {
        "beta_posterior": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def bayes_decision_wrapped(posterior_a: BetaPosterior, posterior_b: BetaPosterior) -> Tuple[str, dict]:
    """Tool wrapper for ``bayes_decision``.

    Pick A or B by posterior evidence.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: a3_bayes_decision")
    kwargs = {'posterior_a': posterior_a, 'posterior_b': posterior_b}
    try:
        result = bayes_decision(**kwargs)
    except Exception as exc:
        return f"Tool a3_bayes_decision failed: {exc}", {
            "bayes_decision": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "a3_bayes_decision: ok"
    return content, {
        "bayes_decision": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def normal_means_posterior_wrapped(samples_a: Sequence[float], samples_b: Sequence[float]) -> Tuple[str, dict]:
    """Tool wrapper for ``normal_means_posterior``.

    Build a normal-normal conjugate posterior for two samples.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: a3_normal_means_posterior")
    kwargs = {'samples_a': samples_a, 'samples_b': samples_b}
    try:
        result = normal_means_posterior(**kwargs)
    except Exception as exc:
        return f"Tool a3_normal_means_posterior failed: {exc}", {
            "normal_means_posterior": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "a3_normal_means_posterior: ok"
    return content, {
        "normal_means_posterior": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


BAYESIAN_ANALYSIS_TOOLS = [
    beta_posterior_wrapped,
    bayes_decision_wrapped,
    normal_means_posterior_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_bayesian_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the A3 agent."""
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
        tools=BAYESIAN_ANALYSIS_TOOLS,
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
        logger.info("    * RUN REACT AGENT FOR A3")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [("system", "You are the A3 agent. Use the available tools to complete the user's request.")] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING A3 RESULTS")
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


class BayesianAnalysisAgent(BaseAgent):
    """OO wrapper for the A3 agent (node type ``model.bayesian_update``)."""

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
        return make_bayesian_agent(**self._params)

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
    "BayesianAnalysisAgent",
    "make_bayesian_agent",
    "BAYESIAN_ANALYSIS_TOOLS",
]
