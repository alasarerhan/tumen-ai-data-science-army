from __future__ import annotations

"""OrchestratorAgent — top-level meta-agent for multi-agent workflow management (M22).

The OrchestratorAgent is the highest-level agent in the platform.  It:

1. Accepts a **natural-language goal** *or* a pre-built **WorkflowSpec**.
2. Uses :class:`~ai_data_science_team.workflow_resolver.WorkflowResolver` to
   determine the execution scenario and, for the *Dynamic* scenario, generates
   a WorkflowSpec from the goal using the LLM.
3. Delegates step-by-step execution to
   :class:`~ai_data_science_team.runtime_engine.RuntimeEngine`, which provides
   retry + back-off, fallback chain, circuit breaker, checkpoint/resume, and
   :class:`~ai_data_science_team.signals.WorkflowSignal`-based optional
   user intervention.
4. Produces a human-readable summary of the completed run using the LLM.

Three execution scenarios
--------------------------
* **Dynamic**    — NL goal → LLM generates spec → RuntimeEngine executes.
* **Supervised** — caller supplies spec → RuntimeEngine executes.
* **Manual**     — caller supplies spec + manages execution themselves.

HITL design
-----------
The pipeline **never blocks** waiting for the user.  At any point the user
can emit a :class:`~ai_data_science_team.signals.WorkflowSignal` (SKIP,
MODIFY, ANNOTATE, CANCEL) via the ``signal_store``; the RuntimeEngine polls
for signals before each step.  Notification is sent only when all automatic
recovery options are exhausted.

Extends
-------
:class:`~ai_data_science_team.templates.BaseAgent`

Usage
-----
::

    from langchain_openai import ChatOpenAI  # noqa: E402, F401
    from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent  # noqa: E402, F401
    from ai_data_science_team.agent_registry import AgentRegistry  # noqa: E402, F401

    llm = ChatOpenAI(model="gpt-4o-mini")

    # Inject how to actually run a sub-agent
    def run_agent(agent_name, instruction, context):
        meta = AgentRegistry.get(agent_name)
        agent = meta.agent_class(model=llm)
        return agent.invoke_agent(user_instructions=instruction)

    orch = OrchestratorAgent(
        model=llm,
        agent_executor=run_agent,
    )

    orch.invoke_agent(
        user_instructions="Load sales.csv and generate an EDA report with key insights."
    )

    logger.info(orch.get_ai_message())
    logger.info(orch.get_run_result())
"""
import json  # noqa: E402, F401
import logging  # noqa: E402, F401
from typing import (  # noqa: E402
    Any,  # noqa: E402, F401
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
)

from langchain_core.messages import (  # noqa: E402, F401
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langgraph.graph import END, START, StateGraph  # noqa: E402, F401
from langgraph.graph.message import add_messages  # noqa: E402, F401
from typing_extensions import Annotated, TypedDict  # noqa: E402, F401

try:
    from IPython.display import Markdown  # noqa: E402, F401
except ImportError:
    Markdown = None  # type: ignore[assignment,misc]

from ai_data_science_team.agent_registry import AgentRegistry  # noqa: E402, F401
from ai_data_science_team.context_store import ContextStore  # noqa: E402, F401
from ai_data_science_team.runtime_engine import RunResult, RuntimeEngine  # noqa: E402, F401
from ai_data_science_team.signals import SignalStore, get_signal_store  # noqa: E402, F401
from ai_data_science_team.templates import BaseAgent  # noqa: E402, F401
from ai_data_science_team.utils.regex import format_agent_name  # noqa: E402, F401
from ai_data_science_team.workflow_resolver import (  # noqa: E402, F401
    WorkflowResolver,
    validate_spec,
)

logger = logging.getLogger(__name__)

AGENT_NAME = "orchestrator_agent"

# ---------------------------------------------------------------------------
# Default agent executor
# ---------------------------------------------------------------------------


def _default_agent_executor(
    agent_name: str,
    instruction: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """No-op executor for dry-run / planning mode.

    Returns a dict describing what *would* be executed.  Replace this with
    a real executor when deploying in production.
    """
    return {
        "agent": agent_name,
        "instruction": instruction,
        "status": "dry_run",
        "note": "No real agent_executor provided; this is a planning dry-run.",
    }


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def _build_orchestrator_graph(
    model: Any,
    resolver: WorkflowResolver,
    engine: RuntimeEngine,
    context_store: ContextStore,
    workflow_spec: Optional[Dict[str, Any]],
    scenario: Optional[str],
    managed_by_user: bool,
    session_id: str,
) -> Any:
    """Build and compile the OrchestratorAgent state graph."""

    # ------------------------------------------------------------------ state

    class OrchestratorState(TypedDict):
        messages: Annotated[Sequence[BaseMessage], add_messages]
        user_instructions: str
        workflow_spec: Dict[str, Any]
        scenario: str
        run_result: Dict[str, Any]
        orchestrator_log: List[str]

    # ------------------------------------------------------------------ nodes

    def prepare(state: OrchestratorState) -> Dict[str, Any]:
        logger.info(format_agent_name("OrchestratorAgent"))
        logger.info("    * PREPARE")
        if state.get("messages"):
            return {}
        instructions = state.get("user_instructions", "")
        return {
            "messages": [HumanMessage(content=instructions)],
            "orchestrator_log": ["Orchestrator starting."],
        }

    def resolve(state: OrchestratorState) -> Dict[str, Any]:
        logger.info("    * RESOLVE SCENARIO + WORKFLOW SPEC")
        log: List[str] = list(state.get("orchestrator_log") or [])

        # Use injected spec or fall back to what's in state
        user_spec = workflow_spec or state.get("workflow_spec") or {}
        user_goal = state.get("user_instructions", "")

        result = resolver.resolve(
            user_goal=user_goal if not user_spec else None,
            workflow_spec=user_spec or None,
            scenario=scenario,
            managed_by_user=managed_by_user,
        )

        resolved_scenario: str = result["scenario"]
        resolved_spec: Dict[str, Any] = result["spec"]
        errors: List[str] = result["errors"]

        if errors:
            log.append(f"WorkflowSpec validation errors: {errors}")
            msg = "⚠️ **WorkflowSpec issues detected:**\n" + "\n".join(f"- {e}" for e in errors)
        else:
            step_count = len(resolved_spec.get("steps", []))
            log.append(
                f"Scenario: {resolved_scenario} | Steps: {step_count} | "
                f"Workflow: {resolved_spec.get('name', '?')}"
            )
            msg = (
                f"**Scenario:** `{resolved_scenario}`  \n"
                f"**Workflow:** {resolved_spec.get('name', '?')}  \n"
                f"**Steps:** {step_count}"
            )

        return {
            "scenario": resolved_scenario,
            "workflow_spec": resolved_spec,
            "orchestrator_log": log,
            "messages": [AIMessage(content=msg, name=AGENT_NAME)],
        }

    def execute(state: OrchestratorState) -> Dict[str, Any]:
        logger.info("    * EXECUTE WORKFLOW")
        log: List[str] = list(state.get("orchestrator_log") or [])
        spec = state.get("workflow_spec") or {}
        current_scenario = state.get("scenario", "supervised")

        if not spec or validate_spec(spec):
            log.append("Execution skipped — invalid or missing WorkflowSpec.")
            return {
                "run_result": {
                    "status": "skipped",
                    "reason": "Invalid or missing WorkflowSpec.",
                },
                "orchestrator_log": log,
            }

        try:
            run: RunResult = engine.run(
                spec=spec,
                session_id=session_id,
                scenario=current_scenario,
            )
            run_dict = run.to_dict()
            log.append(
                f"Run complete: {run.status} | "
                f"success={run.success_count}, failed={run.failed_count}, "
                f"skipped={run.skipped_count}"
            )
        except Exception as exc:  # noqa: BLE001
            run_dict = {"status": "error", "error": str(exc)}
            log.append(f"RuntimeEngine raised exception: {exc}")

        return {
            "run_result": run_dict,
            "orchestrator_log": log,
        }

    def summarize(state: OrchestratorState) -> Dict[str, Any]:
        logger.info("    * SUMMARIZE RESULTS")
        run_result = state.get("run_result") or {}
        spec = state.get("workflow_spec") or {}
        current_scenario = state.get("scenario", "supervised")
        log: List[str] = list(state.get("orchestrator_log") or [])

        # Build summary context for LLM
        run_summary = json.dumps(
            {k: v for k, v in run_result.items() if k != "steps"},
            indent=2,
            default=str,
        )
        steps_summary = json.dumps(
            run_result.get("steps", []),
            indent=2,
            default=str,
        )[:2000]

        system_msg = SystemMessage(
            content=(
                "You are the OrchestratorAgent summarizing a completed workflow run. "
                "Be concise: 3-5 bullet points covering status, key outputs, and any issues. "
                "Use Markdown formatting."
            )
        )
        human_msg = HumanMessage(
            content=(
                f"Workflow: {spec.get('name', '?')}\n"
                f"Scenario: {current_scenario}\n"
                f"Run result:\n{run_summary}\n\n"
                f"Step details:\n{steps_summary}\n\n"
                "Provide a concise summary of what was accomplished and any issues."
            )
        )

        try:
            ai_response = model.invoke([system_msg, human_msg])
            summary_text = getattr(ai_response, "content", str(ai_response))
        except Exception as exc:  # noqa: BLE001
            status = run_result.get("status", "unknown")
            ok = run_result.get("success_count", 0)
            fail = run_result.get("failed_count", 0)
            summary_text = (
                f"**Workflow complete** — status: `{status}`  \n"
                f"✅ {ok} steps succeeded, ❌ {fail} steps failed."
            )
            log.append(f"LLM summarization failed ({exc}); using fallback summary.")

        log.append("Summarization complete.")
        return {
            "messages": [AIMessage(content=summary_text, name=AGENT_NAME)],
            "orchestrator_log": log,
        }

    # ------------------------------------------------------------------ graph

    builder = StateGraph(OrchestratorState)
    builder.add_node("prepare", prepare)
    builder.add_node("resolve", resolve)
    builder.add_node("execute", execute)
    builder.add_node("summarize", summarize)

    builder.add_edge(START, "prepare")
    builder.add_edge("prepare", "resolve")
    builder.add_edge("resolve", "execute")
    builder.add_edge("execute", "summarize")
    builder.add_edge("summarize", END)

    return builder.compile(name="OrchestratorAgent")


# ---------------------------------------------------------------------------
# OrchestratorAgent
# ---------------------------------------------------------------------------


class OrchestratorAgent(BaseAgent):
    """Top-level orchestration agent for multi-scenario workflow management.

    Parameters
    ----------
    model : BaseChatModel
        Language model used for Dynamic spec generation and result
        summarization.
    agent_executor : Callable[[str, str, dict], Any], optional
        A callable ``(agent_name, instruction, context) -> output`` that
        instantiates and invokes the named agent for each workflow step.
        Defaults to a dry-run no-op that returns a planning dict.
    workflow_spec : dict | None
        Pre-built WorkflowSpec for Supervised or Manual scenarios.
        When None and *scenario* is not forced, the scenario is auto-detected
        from the input.  # noqa: E402, F401
    scenario : str | None
        Force a specific scenario: ``"dynamic"``, ``"supervised"``, or
        ``"manual"``.  Auto-detected when None.
    managed_by_user : bool
        When True and *workflow_spec* is provided, forces the Manual scenario.
    signal_store : SignalStore | None
        Custom signal store.  Defaults to the global singleton.
    context_store : ContextStore | None
        Custom context store for checkpointing.
    session_id : str | None
        Session id for this run.  Auto-generated (UUID4) when None.
    registry_catalog : list[dict] | None
        Output of ``AgentRegistry.to_catalog()`` passed to WorkflowResolver
        for Dynamic spec generation.  Defaults to ``AgentRegistry.to_catalog()``.
    max_retries : int
        RuntimeEngine retry count per step (default 2).
    backoff_base : float
        RuntimeEngine back-off base seconds (default 1.0).
    cb_threshold : int
        RuntimeEngine circuit-breaker failure threshold (default 3).
    graceful_degradation : bool
        RuntimeEngine graceful degradation flag (default True).
    log : bool
        Enable verbose logging (default False).

    Examples
    --------
    >>> from langchain_openai import ChatOpenAI
    >>> from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent
    >>> llm = ChatOpenAI(model="gpt-4o-mini")
    >>> orch = OrchestratorAgent(model=llm)
    >>> orch.invoke_agent("Analyse sales.csv and generate a monthly trend report.")
    >>> logger.info(orch.get_ai_message())
    """

    def __init__(
        self,
        model: Any,
        agent_executor: Optional[Callable[[str, str, Dict[str, Any]], Any]] = None,
        workflow_spec: Optional[Dict[str, Any]] = None,
        scenario: Optional[str] = None,
        managed_by_user: bool = False,
        signal_store: Optional[SignalStore] = None,
        context_store: Optional[ContextStore] = None,
        session_id: Optional[str] = None,
        registry_catalog: Optional[List[Dict[str, Any]]] = None,
        max_retries: int = 2,
        backoff_base: float = 1.0,
        cb_threshold: int = 3,
        graceful_degradation: bool = True,
        log: bool = False,
    ) -> None:
        import uuid  # noqa: E402, F401

        self._params = {
            "model": model,
            "agent_executor": agent_executor or _default_agent_executor,
            "workflow_spec": workflow_spec,
            "scenario": scenario,
            "managed_by_user": managed_by_user,
            "signal_store": signal_store or get_signal_store(),
            "context_store": context_store or ContextStore(),
            "session_id": session_id or str(uuid.uuid4()),
            "registry_catalog": (
                registry_catalog if registry_catalog is not None else AgentRegistry.to_catalog()
            ),
            "max_retries": max_retries,
            "backoff_base": backoff_base,
            "cb_threshold": cb_threshold,
            "graceful_degradation": graceful_degradation,
            "log": log,
        }
        self._compiled_graph = self._make_compiled_graph()
        self.response = None

    # ------------------------------------------------------------------

    def update_params(self, **kwargs: Any) -> None:  # type: ignore[override]
        """Update parameters and rebuild the compiled graph."""
        self._params.update(kwargs)
        self._compiled_graph = self._make_compiled_graph()

    def _make_compiled_graph(self) -> Any:
        self.response = None
        p = self._params

        resolver = WorkflowResolver(
            model=p["model"],
            registry_catalog=p["registry_catalog"],
        )

        engine = RuntimeEngine(
            agent_executor=p["agent_executor"],
            signal_store=p["signal_store"],
            context_store=p["context_store"],
            max_retries=p["max_retries"],
            backoff_base=p["backoff_base"],
            cb_threshold=p["cb_threshold"],
            graceful_degradation=p["graceful_degradation"],
        )

        return _build_orchestrator_graph(
            model=p["model"],
            resolver=resolver,
            engine=engine,
            context_store=p["context_store"],
            workflow_spec=p["workflow_spec"],
            scenario=p["scenario"],
            managed_by_user=p["managed_by_user"],
            session_id=p["session_id"],
        )

    # ------------------------------------------------------------------ public API

    def invoke_agent(
        self,
        user_instructions: str,
        workflow_spec: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        """Run the orchestrator.

        Parameters
        ----------
        user_instructions : str
            Natural-language goal (Dynamic scenario) *or* a plain description
            of what the pre-built *workflow_spec* should accomplish.
        workflow_spec : dict | None
            Override the spec set at construction time for this single
            invocation.
        config : dict | None
            LangGraph run configuration.

        Returns
        -------
        dict or None
            Final agent state dict.
        """
        # Allow per-call spec override
        effective_spec = workflow_spec or self._params.get("workflow_spec")

        self.response = self.invoke(
            input={
                "user_instructions": user_instructions,
                "workflow_spec": effective_spec or {},
                "scenario": self._params.get("scenario", ""),
                "run_result": {},
                "orchestrator_log": [],
            },
            config=config,
            **kwargs,
        )
        return self.response

    # ------------------------------------------------------------------ getters

    def get_ai_message(self, markdown: bool = False) -> Optional[Any]:
        """Return the last AI message from the most recent run."""
        if not self.response:
            return None
        for msg in reversed(self.response.get("messages", [])):
            if isinstance(msg, AIMessage) and getattr(msg, "name", None) == AGENT_NAME:
                text = msg.content
                if markdown and Markdown is not None:
                    return Markdown(text)
                return text
        return None

    def get_run_result(self) -> Dict[str, Any]:
        """Return the RunResult dict from the most recent execution."""
        if not self.response:
            return {}
        return self.response.get("run_result", {})

    def get_workflow_spec(self) -> Dict[str, Any]:
        """Return the resolved WorkflowSpec from the most recent run."""
        if not self.response:
            return {}
        return self.response.get("workflow_spec", {})

    def get_scenario(self) -> str:
        """Return the scenario used in the most recent run."""
        if not self.response:
            return ""
        return self.response.get("scenario", "")

    def get_orchestrator_log(self) -> List[str]:
        """Return the internal log entries from the most recent run."""
        if not self.response:
            return []
        return self.response.get("orchestrator_log", [])

    def get_session_id(self) -> str:
        """Return the session id used for this agent instance."""
        return self._params.get("session_id", "")
