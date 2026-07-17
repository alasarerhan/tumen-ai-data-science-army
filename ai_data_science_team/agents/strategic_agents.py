from __future__ import annotations

"""Strategic Insights Supervisor Agent Ekibi — M18.

Four specialist agents that together produce an automated Strategic Report:

``ResultsSynthesizerAgent``
    Merges outputs from upstream agents, extracts key metrics, computes deltas
    versus a baseline, and ranks findings by impact.
    Tools: ``merge_agent_outputs``, ``extract_key_metrics``, ``compare_results``,
    ``rank_findings``.

``ContextualKnowledgeAgent``
    Builds a structured business context profile, generates clarifying questions
    for the user, and extracts named business entities from free text.
    Tools: ``build_context_profile``, ``generate_clarifying_questions``,
    ``extract_business_entities``.

``NarrativeAgent``
    Synthesises findings and context into a polished executive summary, generates
    individual report sections, and assembles a full report document.
    Tools: ``generate_executive_summary``, ``generate_section``, ``format_report``.

``RecommendationAgent``
    Produces ranked, actionable recommendations, designs A/B experiments, and
    scores actions with an ICE/RICE prioritisation framework.
    Tools: ``generate_recommendations``, ``design_ab_test``, ``prioritize_actions``.

All four agents follow the ``BaseAgent`` (``CompiledStateGraph``) pattern with the
standard ``prepare_messages → run_react_agent → post_process`` graph layout.

Example usage::

    from langchain_openai import ChatOpenAI  # noqa: E402, F401
    from ai_data_science_team.agents.strategic_agents import (  # noqa: E402, F401
        ResultsSynthesizerAgent,
        ContextualKnowledgeAgent,
        NarrativeAgent,
        RecommendationAgent,
    )

    llm = ChatOpenAI(model="gpt-4o-mini")

    synthesizer = ResultsSynthesizerAgent(model=llm)
    synthesizer.invoke_agent(
        user_instructions=(
            "Merge the clustering and forecasting results and rank the top findings."
        ),
        prior_artifacts={
            "ClusteringAgent": {"n_clusters": 3, "silhouette": 0.71},
            "AutoForecastAgent": {"best_model": "AutoARIMA", "rmse": 142.3},
        },
    )
    logger.info(synthesizer.get_ai_message())
    logger.info(synthesizer.get_artifacts())
"""
import logging  # noqa: E402, F401

logger = logging.getLogger(__name__)
from typing import Any, Dict, List, Optional, Sequence  # noqa: E402, F401

from langchain_core.messages import AIMessage, BaseMessage  # noqa: E402, F401
from langgraph.graph import END, START, StateGraph  # noqa: E402, F401
from langgraph.types import Checkpointer  # noqa: E402, F401
from typing_extensions import Annotated, TypedDict  # noqa: E402, F401

try:
    from IPython.display import Markdown  # noqa: E402, F401
except ImportError:
    Markdown = None  # type: ignore[assignment,misc]

from langchain.agents import create_agent  # noqa: E402, F401
from langgraph.graph.message import add_messages  # noqa: E402, F401

from ai_data_science_team.templates import BaseAgent  # noqa: E402, F401
from ai_data_science_team.tools.strategic import (  # noqa: E402, F401
    # ResultsSynthesizer
    merge_agent_outputs,
    extract_key_metrics,
    compare_results,
    rank_findings,
    # ContextualKnowledge
    build_context_profile,
    generate_clarifying_questions,
    extract_business_entities,
    # Narrative
    generate_executive_summary,
    generate_section,
    format_report,
    # Recommendation
    generate_recommendations,
    design_ab_test,
    prioritize_actions,
)
from ai_data_science_team.utils.messages import get_tool_call_names  # noqa: E402, F401
from ai_data_science_team.utils.regex import format_agent_name  # noqa: E402, F401

# ---------------------------------------------------------------------------
# Tool groups
# ---------------------------------------------------------------------------

_RESULTS_SYNTHESIZER_TOOLS = [
    merge_agent_outputs,
    extract_key_metrics,
    compare_results,
    rank_findings,
]

_CONTEXTUAL_KNOWLEDGE_TOOLS = [
    build_context_profile,
    generate_clarifying_questions,
    extract_business_entities,
]

_NARRATIVE_TOOLS = [
    generate_executive_summary,
    generate_section,
    format_report,
]

_RECOMMENDATION_TOOLS = [
    generate_recommendations,
    design_ab_test,
    prioritize_actions,
]

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_RESULTS_SYNTHESIZER_SYSTEM_PROMPT = """You are a senior data analyst responsible for
synthesising outputs from multiple AI agents into a coherent, unified results view.

Available tools:
- **merge_agent_outputs** — Combine artifact dicts from multiple agents into a flat map.
- **extract_key_metrics** — Filter specific metric keys from a merged results dict.
- **compare_results** — Compute deltas between a baseline and current results.
- **rank_findings** — Sort a list of findings by a numeric score field.

**Recommended workflow:**
1. Call ``merge_agent_outputs`` with the raw agent artifacts JSON.
2. Call ``extract_key_metrics`` to isolate the most relevant metrics.
3. If a baseline is available, call ``compare_results`` to highlight improvements
   and regressions.
4. Call ``rank_findings`` to order findings by impact or another criterion.
5. Provide a clear narrative summary of what the merged results reveal, what changed
   vs the baseline, and which findings are most significant.

Always present numbers with appropriate precision and explain what each metric means
in plain language suitable for the intended audience."""

_CONTEXTUAL_KNOWLEDGE_SYSTEM_PROMPT = """You are a business intelligence analyst who
understands both technical data and business strategy.  Your role is to gather and
structure the organisational context needed to make analytical findings actionable.

Available tools:
- **build_context_profile** — Structure company, industry, goal, KPIs, and audience
  information into a reusable profile.
- **generate_clarifying_questions** — Produce targeted questions to fill gaps in
  the business context.
- **extract_business_entities** — Pull KPIs, teams, products, and goals from free text.

**Recommended workflow:**
1. Call ``build_context_profile`` with any known organisational details.
2. Call ``extract_business_entities`` on any provided documents or notes to enrich
   the context profile.
3. Call ``generate_clarifying_questions`` to surface the most important gaps —
   focus on ``business_impact`` questions unless the user specifies otherwise.
4. Present the structured context profile and the clarifying questions to the user
   in a clear, organised format.

Be curious but focused: ask the minimum questions needed for a high-quality report."""

_NARRATIVE_SYSTEM_PROMPT = """You are a strategic communications specialist who
transforms complex analytical findings into clear, compelling reports.

Available tools:
- **generate_executive_summary** — Write a prose executive summary from findings
  and business context.
- **generate_section** — Create a single, well-structured report section
  (findings, methodology, risks, next_steps, context, recommendations, appendix).
- **format_report** — Assemble multiple sections into a complete report document.

**Recommended workflow:**
1. Call ``generate_executive_summary`` first to establish the high-level narrative.
2. Call ``generate_section`` for each required section (findings, methodology,
   risks, next_steps are the minimum set).
3. Call ``format_report`` to assemble all sections into the final document with
   a table of contents.
4. Present the final report to the user and offer to adjust tone, depth, or
   specific sections.

Match the writing tone (executive / technical / operational) to the intended
audience specified in the context profile."""

_RECOMMENDATION_SYSTEM_PROMPT = """You are a strategic advisor who converts analytical
findings into concrete, actionable business recommendations.

Available tools:
- **generate_recommendations** — Produce a ranked list of actionable recommendations
  from findings and business context.  # noqa: E402, F401
- **design_ab_test** — Create a statistically rigorous A/B test plan for a hypothesis.
- **prioritize_actions** — Score actions using ICE or RICE frameworks and produce
  a priority-ordered list.

**Recommended workflow:**
1. Call ``generate_recommendations`` to produce the initial recommendation set.
2. Call ``prioritize_actions`` with ICE/RICE scores to rank recommendations by
   expected impact vs effort.
3. For any recommendation that involves a measurable user-facing change, call
   ``design_ab_test`` to propose a validation experiment.
4. Present the prioritised recommendations with clear rationale, expected impact,
   implementation effort, and (where applicable) A/B test plans.

Always link recommendations back to the business goal and KPIs from the context
profile.  Quantify expected impact where possible."""


# ---------------------------------------------------------------------------
# Shared graph factory
# ---------------------------------------------------------------------------


def _build_strategic_graph(
    agent_name: str,
    tools: List[Any],
    model: Any,
    create_react_agent_kwargs: Dict,
    invoke_react_agent_kwargs: Dict,
    checkpointer: Optional[Checkpointer],
    system_prompt: str,
):
    """Build and compile a strategic agent state graph.

    All four strategic agents share this factory to avoid code duplication.
    """

    class GraphState(TypedDict):
        messages: Annotated[Sequence[BaseMessage], add_messages]
        user_instructions: str
        prior_artifacts: Dict[str, Any]
        strategic_artifacts: Dict[str, Any]
        tool_calls: List[str]

    react_agent_graph = create_agent(
        model,
        tools=tools,
        state_schema=GraphState,  # type: ignore[arg-type]
        system_prompt=system_prompt,
        checkpointer=checkpointer,
        **create_react_agent_kwargs,
    )

    # ---- nodes ------------------------------------------------------------

    def prepare_messages(state: GraphState):
        logger.info(format_agent_name(agent_name))
        logger.info("    * PREPARE MESSAGES")
        if state.get("messages"):
            return {}
        instructions = state.get("user_instructions", "Perform strategic analysis.")
        prior = state.get("prior_artifacts", {})
        if prior:
            import json as _json  # noqa: E402, F401
            ctx = f"\n\nPrior agent artifacts available:\n{_json.dumps(prior, indent=2, default=str)[:2000]}"
        else:
            ctx = ""
        return {"messages": [("user", f"{instructions}{ctx}")]}

    def run_react_agent(state: GraphState):
        logger.info(f"    * RUN REACT TOOL-CALLING AGENT [{agent_name.upper()}]")
        response = react_agent_graph.invoke(state, **invoke_react_agent_kwargs)  # type: ignore[arg-type]
        tool_names = get_tool_call_names(response.get("messages", []))
        return {
            "messages": response.get("messages", []),
            "tool_calls": tool_names,
        }

    def post_process(state: GraphState):
        logger.info("    * POST PROCESS")
        artifacts: Dict[str, Any] = {}
        for msg in state.get("messages", []):
            if hasattr(msg, "artifact") and isinstance(msg.artifact, dict):
                key = str(getattr(msg, "name", "result"))
                artifacts[key] = msg.artifact
        return {"strategic_artifacts": artifacts}

    # ---- graph wiring -----------------------------------------------------

    builder = StateGraph(GraphState)
    builder.add_node("prepare_messages", prepare_messages)
    builder.add_node("run_react_agent", run_react_agent)
    builder.add_node("post_process", post_process)

    builder.add_edge(START, "prepare_messages")
    builder.add_edge("prepare_messages", "run_react_agent")
    builder.add_edge("run_react_agent", "post_process")
    builder.add_edge("post_process", END)

    return builder.compile(checkpointer=checkpointer, name=agent_name)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _extract_ai_message(response: Optional[Dict], markdown: bool = False) -> Optional[Any]:
    if not response:
        return None
    for msg in reversed(response.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content:
            text = msg.content
            if markdown and Markdown is not None:
                return Markdown(text)  # type: ignore[return-value]
            return text
    return None


def _extract_artifacts(response: Optional[Dict]) -> Dict[str, Any]:
    if not response:
        return {}
    return response.get("strategic_artifacts", {})


def _extract_tool_calls(response: Optional[Dict]) -> List[str]:
    if not response:
        return []
    return response.get("tool_calls", [])


# ---------------------------------------------------------------------------
# ResultsSynthesizerAgent
# ---------------------------------------------------------------------------


class ResultsSynthesizerAgent(BaseAgent):
    """Agent that merges and synthesises outputs from multiple upstream agents.

    Parameters
    ----------
    model : BaseChatModel
        Language model powering the ReAct loop.
    create_react_agent_kwargs : dict, optional
        Extra keyword arguments forwarded to ``create_agent``.
    invoke_react_agent_kwargs : dict, optional
        Extra keyword arguments forwarded to the react-agent graph's ``invoke``.
    checkpointer : Checkpointer, optional
        LangGraph checkpointer for persistence / HITL.
    system_prompt : str, optional
        Override the default system prompt.
    """

    def __init__(
        self,
        model: Any,
        create_react_agent_kwargs: Optional[Dict] = None,
        invoke_react_agent_kwargs: Optional[Dict] = None,
        checkpointer: Optional[Checkpointer] = None,
        system_prompt: Optional[str] = None,
    ):
        self._params = {
            "model": model,
            "create_react_agent_kwargs": create_react_agent_kwargs or {},
            "invoke_react_agent_kwargs": invoke_react_agent_kwargs or {},
            "checkpointer": checkpointer,
            "system_prompt": system_prompt or _RESULTS_SYNTHESIZER_SYSTEM_PROMPT,
        }
        self._compiled_graph = self._make_compiled_graph()
        self.response = None

    def _make_compiled_graph(self):
        self.response = None
        return _build_strategic_graph(
            agent_name="ResultsSynthesizerAgent",
            tools=_RESULTS_SYNTHESIZER_TOOLS,
            model=self._params["model"],
            create_react_agent_kwargs=self._params["create_react_agent_kwargs"],
            invoke_react_agent_kwargs=self._params["invoke_react_agent_kwargs"],
            checkpointer=self._params["checkpointer"],
            system_prompt=self._params["system_prompt"],
        )

    def update_params(self, **kwargs):
        for k, v in kwargs.items():
            self._params[k] = v
        self._compiled_graph = self._make_compiled_graph()

    def invoke_agent(
        self,
        user_instructions: str,
        prior_artifacts: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """Run the results synthesiser end-to-end.

        Parameters
        ----------
        user_instructions : str
            Natural-language task description.
        prior_artifacts : dict, optional
            Mapping of ``{agent_name: artifact_dict}`` from upstream agents.
        **kwargs
            Forwarded to ``self.invoke()``.
        """
        return self.invoke(
            input={
                "user_instructions": user_instructions,
                "prior_artifacts": prior_artifacts or {},
                "strategic_artifacts": {},
                "tool_calls": [],
            },
            **kwargs,
        )

    def get_ai_message(self, markdown: bool = False) -> Optional[Any]:
        """Return the last AI text response."""
        return _extract_ai_message(self.response, markdown=markdown)

    def get_artifacts(self) -> Dict[str, Any]:
        """Return accumulated strategic artefacts from the last run."""
        return _extract_artifacts(self.response)

    def get_tool_calls(self) -> List[str]:
        """Return list of tool names invoked in the last run."""
        return _extract_tool_calls(self.response)


# ---------------------------------------------------------------------------
# ContextualKnowledgeAgent
# ---------------------------------------------------------------------------


class ContextualKnowledgeAgent(BaseAgent):
    """Agent that builds business context profiles and generates clarifying questions.

    Parameters
    ----------
    model : BaseChatModel
        Language model powering the ReAct loop.
    create_react_agent_kwargs : dict, optional
    invoke_react_agent_kwargs : dict, optional
    checkpointer : Checkpointer, optional
    system_prompt : str, optional
    """

    def __init__(
        self,
        model: Any,
        create_react_agent_kwargs: Optional[Dict] = None,
        invoke_react_agent_kwargs: Optional[Dict] = None,
        checkpointer: Optional[Checkpointer] = None,
        system_prompt: Optional[str] = None,
    ):
        self._params = {
            "model": model,
            "create_react_agent_kwargs": create_react_agent_kwargs or {},
            "invoke_react_agent_kwargs": invoke_react_agent_kwargs or {},
            "checkpointer": checkpointer,
            "system_prompt": system_prompt or _CONTEXTUAL_KNOWLEDGE_SYSTEM_PROMPT,
        }
        self._compiled_graph = self._make_compiled_graph()
        self.response = None

    def _make_compiled_graph(self):
        self.response = None
        return _build_strategic_graph(
            agent_name="ContextualKnowledgeAgent",
            tools=_CONTEXTUAL_KNOWLEDGE_TOOLS,
            model=self._params["model"],
            create_react_agent_kwargs=self._params["create_react_agent_kwargs"],
            invoke_react_agent_kwargs=self._params["invoke_react_agent_kwargs"],
            checkpointer=self._params["checkpointer"],
            system_prompt=self._params["system_prompt"],
        )

    def update_params(self, **kwargs):
        for k, v in kwargs.items():
            self._params[k] = v
        self._compiled_graph = self._make_compiled_graph()

    def invoke_agent(
        self,
        user_instructions: str,
        prior_artifacts: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """Run the contextual knowledge agent end-to-end.

        Parameters
        ----------
        user_instructions : str
            Natural-language task description.
        prior_artifacts : dict, optional
            Any upstream information to provide as context.
        **kwargs
            Forwarded to ``self.invoke()``.
        """
        return self.invoke(
            input={
                "user_instructions": user_instructions,
                "prior_artifacts": prior_artifacts or {},
                "strategic_artifacts": {},
                "tool_calls": [],
            },
            **kwargs,
        )

    def get_ai_message(self, markdown: bool = False) -> Optional[Any]:
        return _extract_ai_message(self.response, markdown=markdown)

    def get_artifacts(self) -> Dict[str, Any]:
        return _extract_artifacts(self.response)

    def get_tool_calls(self) -> List[str]:
        return _extract_tool_calls(self.response)


# ---------------------------------------------------------------------------
# NarrativeAgent
# ---------------------------------------------------------------------------


class NarrativeAgent(BaseAgent):
    """Agent that writes executive summaries, report sections, and full reports.

    Parameters
    ----------
    model : BaseChatModel
        Language model powering the ReAct loop.
    create_react_agent_kwargs : dict, optional
    invoke_react_agent_kwargs : dict, optional
    checkpointer : Checkpointer, optional
    system_prompt : str, optional
    """

    def __init__(
        self,
        model: Any,
        create_react_agent_kwargs: Optional[Dict] = None,
        invoke_react_agent_kwargs: Optional[Dict] = None,
        checkpointer: Optional[Checkpointer] = None,
        system_prompt: Optional[str] = None,
    ):
        self._params = {
            "model": model,
            "create_react_agent_kwargs": create_react_agent_kwargs or {},
            "invoke_react_agent_kwargs": invoke_react_agent_kwargs or {},
            "checkpointer": checkpointer,
            "system_prompt": system_prompt or _NARRATIVE_SYSTEM_PROMPT,
        }
        self._compiled_graph = self._make_compiled_graph()
        self.response = None

    def _make_compiled_graph(self):
        self.response = None
        return _build_strategic_graph(
            agent_name="NarrativeAgent",
            tools=_NARRATIVE_TOOLS,
            model=self._params["model"],
            create_react_agent_kwargs=self._params["create_react_agent_kwargs"],
            invoke_react_agent_kwargs=self._params["invoke_react_agent_kwargs"],
            checkpointer=self._params["checkpointer"],
            system_prompt=self._params["system_prompt"],
        )

    def update_params(self, **kwargs):
        for k, v in kwargs.items():
            self._params[k] = v
        self._compiled_graph = self._make_compiled_graph()

    def invoke_agent(
        self,
        user_instructions: str,
        prior_artifacts: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """Run the narrative agent end-to-end.

        Parameters
        ----------
        user_instructions : str
            Natural-language task description (e.g. "Write a 3-section report …").
        prior_artifacts : dict, optional
            Findings, metrics, and context profile to incorporate.
        **kwargs
            Forwarded to ``self.invoke()``.
        """
        return self.invoke(
            input={
                "user_instructions": user_instructions,
                "prior_artifacts": prior_artifacts or {},
                "strategic_artifacts": {},
                "tool_calls": [],
            },
            **kwargs,
        )

    def get_ai_message(self, markdown: bool = False) -> Optional[Any]:
        return _extract_ai_message(self.response, markdown=markdown)

    def get_artifacts(self) -> Dict[str, Any]:
        return _extract_artifacts(self.response)

    def get_tool_calls(self) -> List[str]:
        return _extract_tool_calls(self.response)


# ---------------------------------------------------------------------------
# RecommendationAgent
# ---------------------------------------------------------------------------


class RecommendationAgent(BaseAgent):
    """Agent that generates recommendations, designs A/B tests, and prioritises actions.

    Parameters
    ----------
    model : BaseChatModel
        Language model powering the ReAct loop.
    create_react_agent_kwargs : dict, optional
    invoke_react_agent_kwargs : dict, optional
    checkpointer : Checkpointer, optional
    system_prompt : str, optional
    """

    def __init__(
        self,
        model: Any,
        create_react_agent_kwargs: Optional[Dict] = None,
        invoke_react_agent_kwargs: Optional[Dict] = None,
        checkpointer: Optional[Checkpointer] = None,
        system_prompt: Optional[str] = None,
    ):
        self._params = {
            "model": model,
            "create_react_agent_kwargs": create_react_agent_kwargs or {},
            "invoke_react_agent_kwargs": invoke_react_agent_kwargs or {},
            "checkpointer": checkpointer,
            "system_prompt": system_prompt or _RECOMMENDATION_SYSTEM_PROMPT,
        }
        self._compiled_graph = self._make_compiled_graph()
        self.response = None

    def _make_compiled_graph(self):
        self.response = None
        return _build_strategic_graph(
            agent_name="RecommendationAgent",
            tools=_RECOMMENDATION_TOOLS,
            model=self._params["model"],
            create_react_agent_kwargs=self._params["create_react_agent_kwargs"],
            invoke_react_agent_kwargs=self._params["invoke_react_agent_kwargs"],
            checkpointer=self._params["checkpointer"],
            system_prompt=self._params["system_prompt"],
        )

    def update_params(self, **kwargs):
        for k, v in kwargs.items():
            self._params[k] = v
        self._compiled_graph = self._make_compiled_graph()

    def invoke_agent(
        self,
        user_instructions: str,
        prior_artifacts: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """Run the recommendation agent end-to-end.

        Parameters
        ----------
        user_instructions : str
            Natural-language task description.
        prior_artifacts : dict, optional
            Ranked findings and context profile from upstream agents.
        **kwargs
            Forwarded to ``self.invoke()``.
        """
        return self.invoke(
            input={
                "user_instructions": user_instructions,
                "prior_artifacts": prior_artifacts or {},
                "strategic_artifacts": {},
                "tool_calls": [],
            },
            **kwargs,
        )

    def get_ai_message(self, markdown: bool = False) -> Optional[Any]:
        return _extract_ai_message(self.response, markdown=markdown)

    def get_artifacts(self) -> Dict[str, Any]:
        return _extract_artifacts(self.response)

    def get_tool_calls(self) -> List[str]:
        return _extract_tool_calls(self.response)
