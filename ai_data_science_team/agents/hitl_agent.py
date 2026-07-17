from __future__ import annotations

"""Human-in-the-Loop (HITL) Approval Gate Agent — M17.

``ApprovalGateAgent``
    A generic approval-aware agent that wraps any analytical task with a
    human-review interrupt.  When ``human_in_the_loop=True`` the graph pauses
    at the **human_review** node and waits for a ``Command(resume=...)`` from
    the user before proceeding to ``post_process``.

Graph topology
--------------

.. code-block:: text

    START
      │
      ▼
    prepare_messages
      │
      ▼
    run_react_agent   ◄─────────────────────────────┐
      │                                              │  (modifications)
      ▼                                              │
    human_review ── (approved / "yes") ─► post_process ─► END
      │
      └─ (modifications) ─────────────────────────► run_react_agent

When ``human_in_the_loop=False`` the **human_review** node is skipped
entirely: ``run_react_agent`` connects directly to ``post_process``.

Example usage
-------------

::

    from langchain_openai import ChatOpenAI  # noqa: E402, F401
    from langgraph.checkpoint.memory import MemorySaver  # noqa: E402, F401
    from ai_data_science_team.agents.hitl_agent import ApprovalGateAgent  # noqa: E402, F401

    llm = ChatOpenAI(model="gpt-4o-mini")

    agent = ApprovalGateAgent(model=llm, human_in_the_loop=True)

    config = {"configurable": {"thread_id": "session-42"}}

    # First invocation — pauses at human_review
    agent.invoke_agent(
        user_instructions="Summarise the churn analysis results for approval.",
        prior_artifacts={"ChurnModel": {"auc": 0.91, "accuracy": 0.85}},
        config=config,
    )

    # Inspect what the LLM produced
    state = agent.get_state(config)
    approval_prompt = state.tasks[-1].interrupts[-1].value
    logger.info(approval_prompt)

    # Resume with approval
    agent.invoke(Command(resume="yes"), config=config)

    logger.info(agent.get_ai_message())
    logger.info(agent.get_artifacts())
"""
from typing import (Dict, List, Optional, Sequence)  # noqa: E402
import logging  # noqa: E402, F401

logger = logging.getLogger(__name__)
import json  # noqa: E402, F401
from typing import Any  # noqa: E402, F401

from langchain_core.messages import AIMessage, BaseMessage  # noqa: E402, F401
from langgraph.checkpoint.memory import MemorySaver  # noqa: E402, F401
from langgraph.graph import END, START, StateGraph  # noqa: E402, F401
from langgraph.types import Checkpointer, Command, interrupt  # noqa: E402, F401
from typing_extensions import Annotated, TypedDict  # noqa: E402, F401

try:
    from IPython.display import Markdown  # noqa: E402, F401
except ImportError:
    Markdown = None  # type: ignore[assignment,misc]

from langchain.agents import create_agent  # noqa: E402, F401
from langgraph.graph.message import add_messages  # noqa: E402, F401

from ai_data_science_team.templates import BaseAgent  # noqa: E402, F401
from ai_data_science_team.tools.hitl import (  # noqa: E402, F401
    check_approval_status,
    create_approval_request,
    format_approval_notification,
    log_approval_decision,
    summarize_for_approval,
)
from ai_data_science_team.utils.messages import get_tool_call_names  # noqa: E402, F401
from ai_data_science_team.utils.regex import format_agent_name  # noqa: E402, F401

# ---------------------------------------------------------------------------
# Default tool list
# ---------------------------------------------------------------------------

_HITL_TOOLS = [
    create_approval_request,
    format_approval_notification,
    check_approval_status,
    log_approval_decision,
    summarize_for_approval,
]

# ---------------------------------------------------------------------------
# Default system prompt
# ---------------------------------------------------------------------------

_HITL_SYSTEM_PROMPT = """You are an Approval Gate Agent.  Your role is to help
human reviewers understand what an AI pipeline step is about to do, so they can
approve or request modifications before the step is executed.

Available tools:
- **create_approval_request** — Build a structured approval-request record with a
  unique id, step name, description, data summary, risk level, and agent name.
- **format_approval_notification** — Convert an approval-request dict into a
  human-readable Markdown notification ready for display in a UI, email, or Slack
  message.
- **check_approval_status** — Look up the current status of an approval request by
  its id (pending / approved / rejected / modified).
- **log_approval_decision** — Record a human decision against a request id and
  update the approval store.  Always call this after the human responds.
- **summarize_for_approval** — Produce a concise bullet-point summary of an agent's
  output artifact dict to make the review fast for the human.

**Recommended workflow:**
1. Call ``summarize_for_approval`` on any prior agent artifacts to give the reviewer
   a concise overview of what was produced.
2. Call ``create_approval_request`` with a clear step name, description, and risk
   level.
3. Call ``format_approval_notification`` to generate the notification shown to the
   reviewer.
4. Present the notification to the user and ask them to respond with 'yes' to
   approve or provide modification instructions.

After the human_review interrupt is resolved:
5. Call ``log_approval_decision`` to record the final decision.
6. If approved, provide a brief confirmation message.
7. If modifications were requested, acknowledge the instructions and indicate that
   the pipeline will be adjusted accordingly.

Always be clear, concise, and professional.  Quantify risk where possible."""

# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def _build_hitl_graph(
    model: Any,
    create_react_agent_kwargs: Dict,
    invoke_react_agent_kwargs: Dict,
    checkpointer: Optional[Checkpointer],
    system_prompt: str,
    human_in_the_loop: bool,
    tools: List[Any],
) -> Any:
    """Build and compile the ApprovalGate state graph."""

    class GraphState(TypedDict):
        messages: Annotated[Sequence[BaseMessage], add_messages]
        user_instructions: str
        prior_artifacts: Dict[str, Any]
        approval_artifacts: Dict[str, Any]
        tool_calls: List[str]

    react_agent_graph = create_agent(
        model,
        tools=tools,
        state_schema=GraphState,  # type: ignore[arg-type]
        system_prompt=system_prompt,
        checkpointer=checkpointer,
        **create_react_agent_kwargs,
    )

    # ------------------------------------------------------------------ nodes

    def prepare_messages(state: GraphState):
        logger.info(format_agent_name("ApprovalGateAgent"))
        logger.info("    * PREPARE MESSAGES")
        if state.get("messages"):
            return {}
        instructions = state.get(
            "user_instructions", "Review the step and create an approval request."
        )
        prior = state.get("prior_artifacts", {})
        if prior:
            ctx = (
                "\n\nPrior agent artifacts available for review:\n"
                + json.dumps(prior, indent=2, default=str)[:2000]
            )
        else:
            ctx = ""
        return {"messages": [("user", f"{instructions}{ctx}")]}

    def run_react_agent(state: GraphState):
        logger.info("    * RUN REACT TOOL-CALLING AGENT [APPROVALGATE]")
        response = react_agent_graph.invoke(state, **invoke_react_agent_kwargs)  # type: ignore[arg-type]
        tool_names = get_tool_call_names(response.get("messages", []))
        return {
            "messages": response.get("messages", []),
            "tool_calls": tool_names,
        }

    def human_review(state: GraphState) -> Command[str]:
        """Interrupt and wait for human input.

        Returns ``Command(goto="post_process")`` on approval
        or ``Command(goto="run_react_agent", update={...})`` on modification.
        """
        logger.info("    * HUMAN REVIEW")

        # Collect a brief summary of what was produced so far
        last_ai_content = ""
        for msg in reversed(state.get("messages", [])):
            if isinstance(msg, AIMessage) and msg.content:
                last_ai_content = msg.content[:500]
                break

        prompt = (
            "## Approval Gate — Human Review Required\n\n"
            "The AI agent has completed its analysis step.\n\n"
            "### Agent Output Preview\n"
            f"{last_ai_content or '*(no AI message yet)*'}\n\n"
            "---\n"
            "Reply **`yes`** to approve and continue, or provide modification "
            "instructions to revise the output."
        )

        user_input: str = interrupt(value=prompt)

        if user_input.strip().lower() == "yes":
            return Command(goto="post_process")  # type: ignore[return-value]

        # Modification requested — feed updated instructions back
        modifications = "User requested modifications: " + user_input
        current_instructions = state.get("user_instructions") or ""
        updated_instructions = (
            current_instructions + "\n\n" + modifications
            if current_instructions
            else modifications
        )
        return Command(  # type: ignore[return-value]
            goto="run_react_agent",
            update={
                "user_instructions": updated_instructions,
                "messages": [],  # reset messages so prepare is re-run cleanly
            },
        )

    def post_process(state: GraphState):
        logger.info("    * POST PROCESS")
        artifacts: Dict[str, Any] = {}
        for msg in state.get("messages", []):
            if hasattr(msg, "artifact") and isinstance(msg.artifact, dict):
                key = str(getattr(msg, "name", "result"))
                artifacts[key] = msg.artifact
        return {"approval_artifacts": artifacts}

    # -------------------------------------------------------- graph wiring

    builder = StateGraph(GraphState)
    builder.add_node("prepare_messages", prepare_messages)
    builder.add_node("run_react_agent", run_react_agent)
    builder.add_node("post_process", post_process)

    builder.add_edge(START, "prepare_messages")
    builder.add_edge("prepare_messages", "run_react_agent")

    if human_in_the_loop:
        builder.add_node("human_review", human_review)
        builder.add_edge("run_react_agent", "human_review")
        # human_review returns a Command so no explicit edge to post_process needed
    else:
        builder.add_edge("run_react_agent", "post_process")

    builder.add_edge("post_process", END)

    return builder.compile(
        checkpointer=checkpointer,
        name="ApprovalGateAgent",
    )


# ---------------------------------------------------------------------------
# ApprovalGateAgent
# ---------------------------------------------------------------------------


class ApprovalGateAgent(BaseAgent):
    """A human-in-the-loop approval gate agent.

    Wraps any analytical task with an optional human-review interrupt so that
    operators can approve, reject, or request modifications before the pipeline
    continues.

    Parameters
    ----------
    model : BaseChatModel
        Language model powering the ReAct loop.
    tools : list, optional
        Override the default HITL tool list.
    human_in_the_loop : bool, optional
        Whether to insert a ``interrupt``-based human_review node between
        ``run_react_agent`` and ``post_process``. Default ``True``.
        Set to ``False`` for automated / test runs.
    checkpointer : Checkpointer, optional
        LangGraph checkpointer for state persistence across invocations.
        When ``human_in_the_loop=True`` and no checkpointer is supplied a
        ``MemorySaver`` is created automatically.
    create_react_agent_kwargs : dict, optional
        Extra keyword arguments forwarded to ``create_agent``.
    invoke_react_agent_kwargs : dict, optional
        Extra keyword arguments forwarded to the react-agent graph ``invoke``.
    system_prompt : str, optional
        Override the default HITL system prompt.

    Examples
    --------
    >>> from langchain_openai import ChatOpenAI
    >>> agent = ApprovalGateAgent(model=ChatOpenAI(model="gpt-4o-mini"))
    >>> agent.invoke_agent(
    ...     user_instructions="Review and approve the feature engineering plan.",
    ...     config={"configurable": {"thread_id": "1"}},
    ... )
    """

    def __init__(
        self,
        model: Any,
        tools: Optional[List[Any]] = None,
        human_in_the_loop: bool = True,
        checkpointer: Optional[Checkpointer] = None,
        create_react_agent_kwargs: Optional[Dict] = None,
        invoke_react_agent_kwargs: Optional[Dict] = None,
        system_prompt: Optional[str] = None,
    ):
        if human_in_the_loop and checkpointer is None:
            logger.info(
                "ApprovalGateAgent: human_in_the_loop=True requires a checkpointer."
                " Setting checkpointer=MemorySaver()."
            )
            checkpointer = MemorySaver()

        self._params = {
            "model": model,
            "tools": tools if tools is not None else _HITL_TOOLS,
            "human_in_the_loop": human_in_the_loop,
            "checkpointer": checkpointer,
            "create_react_agent_kwargs": create_react_agent_kwargs or {},
            "invoke_react_agent_kwargs": invoke_react_agent_kwargs or {},
            "system_prompt": system_prompt or _HITL_SYSTEM_PROMPT,
        }
        self._compiled_graph = self._make_compiled_graph()
        self.response = None

    # ------------------------------------------------------------------

    def _make_compiled_graph(self):
        self.response = None
        return _build_hitl_graph(
            model=self._params["model"],
            create_react_agent_kwargs=self._params["create_react_agent_kwargs"],
            invoke_react_agent_kwargs=self._params["invoke_react_agent_kwargs"],
            checkpointer=self._params["checkpointer"],
            system_prompt=self._params["system_prompt"],
            human_in_the_loop=self._params["human_in_the_loop"],
            tools=self._params["tools"],
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def invoke_agent(
        self,
        user_instructions: str,
        prior_artifacts: Optional[Dict[str, Any]] = None,
        config: Optional[Dict] = None,
        **kwargs,
    ) -> Optional[Dict]:
        """Run the ApprovalGate agent.

        Parameters
        ----------
        user_instructions : str
            The task description / context to present for review.
        prior_artifacts : dict, optional
            Artifacts produced by upstream agents, passed into the state so the
            HITL tools can summarise them for the reviewer.
        config : dict, optional
            LangGraph run config.  When using ``human_in_the_loop=True`` this
            **must** include ``{"configurable": {"thread_id": "<id>"}}``.
        **kwargs
            Additional keyword arguments forwarded to
            :py:meth:`BaseAgent.invoke`.

        Returns
        -------
        dict or None
            The final agent state dict, or ``None`` if execution was interrupted
            waiting for human input.
        """
        self.response = self.invoke(
            input={
                "user_instructions": user_instructions,
                "prior_artifacts": prior_artifacts or {},
                "approval_artifacts": {},
                "tool_calls": [],
            },
            config=config,
            **kwargs,
        )
        return self.response

    def resume_agent(
        self,
        decision: str,
        config: Optional[Dict] = None,
        **kwargs,
    ) -> Optional[Dict]:
        """Resume a paused (interrupted) graph with a human decision.

        Parameters
        ----------
        decision : str
            Human response.  Pass ``"yes"`` to approve, or a free-text
            modification request (e.g. ``"Please also check for data leakage"``).
        config : dict, optional
            Must match the ``thread_id`` used in :meth:`invoke_agent`.

        Returns
        -------
        dict or None
            The updated agent state.
        """
        self.response = self.invoke(
            input=Command(resume=decision),
            config=config,
            **kwargs,
        )
        return self.response

    # ------------------------------------------------------------------ getters

    def get_ai_message(self, markdown: bool = False) -> Optional[Any]:
        """Return the last AI message from the most recent run.

        Parameters
        ----------
        markdown : bool, optional
            If ``True`` and IPython is available return an ``IPython.display.Markdown``
            object instead of a plain string.

        Returns
        -------
        str | IPython.display.Markdown | None
        """
        if not self.response:
            return None
        for msg in reversed(self.response.get("messages", [])):
            if isinstance(msg, AIMessage) and msg.content:
                text = msg.content
                if markdown and Markdown is not None:
                    return Markdown(text)
                return text
        return None

    def get_artifacts(self) -> Dict[str, Any]:
        """Return the approval artifacts collected during ``post_process``.

        Returns
        -------
        dict
        """
        if not self.response:
            return {}
        return self.response.get("approval_artifacts", {})

    def get_tool_calls(self) -> List[str]:
        """Return the list of tool names called during the last run.

        Returns
        -------
        list[str]
        """
        if not self.response:
            return []
        return self.response.get("tool_calls", [])

    def get_pending_approval(self, config: Optional[Dict] = None) -> Optional[str]:
        """Return the interrupt prompt (approval request text) if the graph
        is currently paused waiting for human input.

        Parameters
        ----------
        config : dict, optional
            The run config used when invoking the agent.

        Returns
        -------
        str | None
            The interrupt value (Markdown prompt) if paused, else ``None``.
        """
        if config is None:
            return None
        try:
            state = self._compiled_graph.get_state(config=config)
            tasks = getattr(state, "tasks", [])
            if tasks:
                interrupts = getattr(tasks[-1], "interrupts", [])
                if interrupts:
                    return getattr(interrupts[-1], "value", None)
        except Exception:
            pass
        return None
