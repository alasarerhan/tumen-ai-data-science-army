from __future__ import annotations

"""
PowerAnalysisAgent
==================

End-to-end experiment-design agent implementing spec **A2** —
"Power Analysis & Experiment Design Agent" from
``docs/AGENT_SPEC_CATALOG.md``.

Capabilities
------------
- Solve any of the four canonical power-analysis problems
  (``N``, ``power``, ``alpha``, ``MDE``) for proportion or continuous
  metrics.
- Required sample size (a priori) with auto test selection.
- Minimum detectable effect (sensitivity) with absolute / relative
  lift inversion.
- Runtime estimation (days needed at given daily traffic + ramp-up).
- Stratification suggestion from a historical dataset (low-cardinality
  candidates skewed or associated with the assignment column).
- One-shot ``design_experiment`` façade that combines all of the above
  into a single artifact.

The deterministic statistical core lives in
:mod:`ai_data_science_team.tools.power_analysis` so it can be reused
outside the LangGraph runtime (workflow engine, batch jobs, ad-hoc
notebooks).

This module wraps that core in ``@tool``-decorated functions and
stitches them into a LangGraph state graph following the same pattern
as ``ABTestingAgent``, ``EDAToolsAgent`` and ``DataQualityAgent``.

Node type
---------
``experiment.design``
"""

import logging  # noqa: E402, F401

logger = logging.getLogger(__name__)
from typing import (  # noqa: E402, F401
    Annotated,
    Any,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    TypedDict,
)

import pandas as pd  # noqa: E402, F401
from IPython.display import Markdown  # noqa: E402, F401
from langchain.agents import create_agent  # noqa: E402, F401
from langchain.tools import tool  # noqa: E402, F401
from langchain_core.messages import AIMessage, BaseMessage  # noqa: E402, F401
from langgraph.graph import END, START, StateGraph  # noqa: E402, F401
from langgraph.graph.message import add_messages  # noqa: E402, F401
from langgraph.prebuilt import InjectedState  # noqa: E402, F401
from langgraph.types import Checkpointer  # noqa: E402, F401

from ai_data_science_team.templates import BaseAgent  # noqa: E402, F401
from ai_data_science_team.tools.power_analysis import (  # noqa: E402, F401
    design_experiment,
    estimate_runtime_days,
    minimum_detectable_effect,
    required_sample_size,
    solve_power,
    suggest_stratification,
)
from ai_data_science_team.utils.messages import get_tool_call_names  # noqa: E402, F401
from ai_data_science_team.utils.regex import format_agent_name  # noqa: E402, F401

AGENT_NAME = "power_analysis_agent"
NODE_TYPE = "experiment.design"


# ---------------------------------------------------------------------------
# LangChain tool wrappers (LLM-callable surface for the react agent)
# ---------------------------------------------------------------------------


@tool(response_format="content_and_artifact")
def pa_solve_power(
    solve_for: str,
    metric_type: str = "proportion",
    baseline_rate: Optional[float] = None,
    baseline_mean: Optional[float] = None,
    baseline_sd: Optional[float] = None,
    expected_treatment_rate: Optional[float] = None,
    expected_lift: Optional[float] = None,
    nobs1: Optional[int] = None,
    alpha: float = 0.05,
    power: float = 0.80,
    ratio: float = 1.0,
    alternative: str = "two-sided",
) -> Tuple[str, Dict]:
    """
    Tool: pa_solve_power
    Description:
        Generic dispatcher: solves one of the four classical power-analysis
        problems (``n`` | ``power`` | ``alpha`` | ``effect_size``) for
        either a proportion metric (z-test) or a continuous metric
        (t-test).

    Args:
        solve_for : One of 'n', 'power', 'alpha', 'effect_size'.
        metric_type : 'proportion' or 'continuous'.
        baseline_rate : Control conversion rate, in (0, 1). Proportion only.
        baseline_mean / baseline_sd : Control mean and pooled SD. Continuous only.
        expected_treatment_rate : Treatment rate (alternative to expected_lift).
        expected_lift : Absolute rate lift OR absolute mean lift.
        nobs1 : Per-arm sample size. Required unless solve_for='n'.
        alpha : Type-I error (default 0.05).
        power : 1 - Type-II error (default 0.80).
        ratio : Treatment-to-control sample size ratio (default 1.0).
        alternative : 'two-sided', 'larger', or 'smaller'.
    """
    logger.info("    * Tool: pa_solve_power")

    result = solve_power(
        solve_for=solve_for,
        metric_type=metric_type,
        baseline_rate=baseline_rate,
        baseline_mean=baseline_mean,
        baseline_sd=baseline_sd,
        expected_treatment_rate=expected_treatment_rate,
        expected_lift=expected_lift,
        nobs1=nobs1,
        alpha=alpha,
        power=power,
        ratio=ratio,
        alternative=alternative,
    )
    content = (
        f"pa_solve_power({solve_for}, {metric_type}): "
        f"solved_value={result['solved_value']}, "
        f"effect_size={result.get('cohen_h', result.get('cohen_d'))}, "
        f"alpha={result['alpha']}, power={result['power']}."
    )
    return content, result


@tool(response_format="content_and_artifact")
def pa_required_sample_size(
    metric_type: str = "proportion",
    baseline_rate: Optional[float] = None,
    baseline_mean: Optional[float] = None,
    baseline_sd: Optional[float] = None,
    expected_treatment_rate: Optional[float] = None,
    expected_lift: Optional[float] = None,
    alpha: float = 0.05,
    power: float = 0.80,
    ratio: float = 1.0,
) -> Tuple[str, Dict]:
    """
    Tool: pa_required_sample_size
    Description:
        A priori power analysis — returns the per-arm sample size needed
        to detect a given effect at ``alpha`` with probability ``power``.
        Wraps :func:`solve_power` with ``solve_for='n'``.

    Args:
        metric_type : 'proportion' or 'continuous'.
        baseline_rate : Control rate, in (0, 1). Proportion only.
        baseline_mean / baseline_sd : Control mean and pooled SD. Continuous only.
        expected_treatment_rate : Treatment rate (alternative to expected_lift).
        expected_lift : Absolute lift.
        alpha : Significance level (default 0.05).
        power  : Desired power (default 0.80).
        ratio  : Treatment-to-control allocation ratio (default 1.0).
    """
    logger.info("    * Tool: pa_required_sample_size")

    result = required_sample_size(
        metric_type=metric_type,
        baseline_rate=baseline_rate,
        baseline_mean=baseline_mean,
        baseline_sd=baseline_sd,
        expected_treatment_rate=expected_treatment_rate,
        expected_lift=expected_lift,
        alpha=alpha,
        power=power,
        ratio=ratio,
    )
    n = result["solved_value"]
    content = (
        f"Required sample size per arm: {n} "
        f"(metric={metric_type}, alpha={alpha}, power={power}, ratio={ratio})."
    )
    return content, result


@tool(response_format="content_and_artifact")
def pa_minimum_detectable_effect(
    nobs1: int,
    metric_type: str = "proportion",
    baseline_rate: Optional[float] = None,
    baseline_mean: Optional[float] = None,
    baseline_sd: Optional[float] = None,
    alpha: float = 0.05,
    power: float = 0.80,
    ratio: float = 1.0,
    alternative: str = "two-sided",
) -> Tuple[str, Dict]:
    """
    Tool: pa_minimum_detectable_effect
    Description:
        Sensitivity analysis — given a fixed per-arm sample size, returns
        the smallest effect (Cohen's ``h`` or ``d``) plus the
        inverted-back absolute / relative lift that the experiment can
        detect at ``alpha`` with probability ``power``.

    Args:
        nobs1 : Per-arm sample size.
        metric_type : 'proportion' or 'continuous'.
        baseline_rate : Control rate, in (0, 1). Proportion only.
        baseline_mean / baseline_sd : Control mean and pooled SD.
            Continuous only.
        alpha : Significance level (default 0.05).
        power  : Desired power (default 0.80).
        ratio  : Treatment-to-control allocation ratio (default 1.0).
        alternative : 'two-sided', 'larger', 'smaller'.
    """
    logger.info("    * Tool: pa_minimum_detectable_effect")

    result = minimum_detectable_effect(
        nobs1=nobs1,
        metric_type=metric_type,
        baseline_rate=baseline_rate,
        baseline_mean=baseline_mean,
        baseline_sd=baseline_sd,
        alpha=alpha,
        power=power,
        ratio=ratio,
        alternative=alternative,
    )
    es = result["effect_size"]
    content = (
        f"MDE @ nobs1={nobs1}: effect_size={es:.6f}, "
        f"absolute_lift={result.get('absolute_lift')}, "
        f"relative_lift={result.get('relative_lift')}."
    )
    return content, result


@tool(response_format="content_and_artifact")
def pa_estimate_runtime(
    required_n_per_arm: int,
    daily_traffic: int,
    num_arms: int = 2,
    traffic_allocation: float = 1.0,
    ramp_up_days: int = 0,
) -> Tuple[str, Dict]:
    """
    Tool: pa_estimate_runtime
    Description:
        Estimates how many calendar days an experiment needs to run,
        given a per-arm sample size requirement, daily eligible traffic
        entering the experiment, the number of variants, the traffic
        allocation fraction and any ramp-up days.

    Args:
        required_n_per_arm : Per-arm N (output of pa_required_sample_size).
        daily_traffic      : Average users entering the experiment per day.
        num_arms           : Number of variants (default 2).
        traffic_allocation : Fraction of total traffic routed in (default 1.0).
        ramp_up_days       : Days where traffic ramps 0→full (default 0).
    """
    logger.info("    * Tool: pa_estimate_runtime")

    result = estimate_runtime_days(
        required_n_per_arm=required_n_per_arm,
        daily_traffic=daily_traffic,
        num_arms=num_arms,
        traffic_allocation=traffic_allocation,
        ramp_up_days=ramp_up_days,
    )
    content = (
        f"Runtime estimate: {result['days_needed']} days "
        f"(required_n_per_arm={required_n_per_arm}, "
        f"daily_eligible_users={result['daily_eligible_users']}, "
        f"ramp_up_days={ramp_up_days})."
    )
    return content, result


@tool(response_format="content_and_artifact")
def pa_suggest_stratification(
    data_raw: Annotated[dict, InjectedState("data_raw")],
    group_column: Optional[str] = None,
    candidate_columns: Optional[List[str]] = None,
    max_cardinality: int = 20,
) -> Tuple[str, Dict]:
    """
    Tool: pa_suggest_stratification
    Description:
        Recommends columns to stratify randomisation on, using a
        historical dataset. A column is suggested when its distribution
        is heavily skewed (top bucket > 40% of rows) OR when it is
        significantly associated with the assignment column
        (chi-square p<0.10). Columns with cardinality > max_cardinality
        or unique-per-row identifiers are skipped.

    Parameters (injected from state):
        data_raw : Historical dataset as dict.

    Args:
        group_column     : Optional variant/assignment column.
        candidate_columns : Optional list to limit assessment.
        max_cardinality  : Maximum allowed cardinality (default 20).
    """
    logger.info("    * Tool: pa_suggest_stratification")

    df = pd.DataFrame(data_raw)
    result = suggest_stratification(
        df,
        group_column=group_column,
        candidate_columns=candidate_columns,
        max_cardinality=max_cardinality,
    )
    recs = result.get("recommendations", [])
    content = (
        f"Stratification suggestions: {len(recs)} "
        f"candidate column(s) (group_column={group_column})."
    )
    if recs:
        content += " Top-3: " + ", ".join(f"{r['column']} (score={r['score']})" for r in recs[:3])
    return content, result


@tool(response_format="content_and_artifact")
def pa_design_experiment(
    metric_type: str = "proportion",
    baseline_rate: Optional[float] = None,
    baseline_mean: Optional[float] = None,
    baseline_sd: Optional[float] = None,
    expected_treatment_rate: Optional[float] = None,
    expected_lift: Optional[float] = None,
    alpha: float = 0.05,
    power: float = 0.80,
    ratio: float = 1.0,
    num_arms: int = 2,
    daily_traffic: Optional[int] = None,
    traffic_allocation: float = 1.0,
    ramp_up_days: int = 0,
    historical_data_raw: Annotated[Optional[dict], InjectedState("historical_data_raw")] = None,
    stratification_group_column: Optional[str] = None,
) -> Tuple[str, Dict]:
    """
    Tool: pa_design_experiment
    Description:
        One-shot experiment design. Combines a priori power analysis,
        runtime estimation and (when ``historical_data_raw`` is supplied)
        stratification suggestion into a single artifact with three
        keys: ``sample_size``, ``design_inputs``, ``runtime`` (and
        optionally ``stratification``).

    Args:
        metric_type : 'proportion' or 'continuous'.
        baseline_rate / expected_treatment_rate / expected_lift :
            Same semantics as in pa_required_sample_size.
        baseline_mean / baseline_sd : Continuous-only inputs.
        alpha / power / ratio / num_arms : Standard power inputs.
        daily_traffic : If > 0, a runtime estimate is included.
        traffic_allocation / ramp_up_days : Runtime inputs.
        historical_data_raw : Optional historical dataset (auto-injected
            from state) used to score stratification candidates.  # noqa: E402, F401
        stratification_group_column : Optional assignment column.
    """
    logger.info("    * Tool: pa_design_experiment")

    historical_df = pd.DataFrame(historical_data_raw) if historical_data_raw is not None else None

    result = design_experiment(
        metric_type=metric_type,
        baseline_rate=baseline_rate,
        baseline_mean=baseline_mean,
        baseline_sd=baseline_sd,
        expected_treatment_rate=expected_treatment_rate,
        expected_lift=expected_lift,
        alpha=alpha,
        power=power,
        ratio=ratio,
        num_arms=num_arms,
        daily_traffic=daily_traffic,
        traffic_allocation=traffic_allocation,
        ramp_up_days=ramp_up_days,
        historical_data=historical_df,
        stratification_group_column=stratification_group_column,
    )
    n = result["sample_size"]["solved_value"]
    days = result.get("runtime", {}).get("days_needed")
    content = (
        f"Experiment design ready: n_per_arm={n}, "
        f"days_needed={days}, "
        f"stratification={'yes' if 'stratification' in result else 'no'}."
    )
    return content, result


POWER_ANALYSIS_TOOLS = [
    pa_solve_power,
    pa_required_sample_size,
    pa_minimum_detectable_effect,
    pa_estimate_runtime,
    pa_suggest_stratification,
    pa_design_experiment,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_power_analysis_agent(
    model: Any,
    alpha: float = 0.05,
    power: float = 0.80,
    ratio: float = 1.0,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    checkpointer: Optional[Checkpointer] = None,
    log_tool_calls: bool = True,
):
    """
    Build the LangGraph StateGraph for the PowerAnalysisAgent.

    Parameters
    ----------
    model : Any
        LangChain LLM supporting tool-calling (e.g. ChatOpenAI).
    alpha : float, default 0.05
        Default significance level injected into state.
    power : float, default 0.80
        Default desired statistical power injected into state.
    ratio : float, default 1.0
        Default treatment-to-control sample size ratio.
    """
    if create_react_agent_kwargs is None:
        create_react_agent_kwargs = {}
    if invoke_react_agent_kwargs is None:
        invoke_react_agent_kwargs = {}

    class GraphState(TypedDict):
        messages: Annotated[Sequence[BaseMessage], add_messages]
        user_instructions: str
        # Optional datasets injected from the caller.
        data_raw: dict
        historical_data_raw: dict
        # Power-analysis defaults propagated to the tools via state.
        alpha: float
        power: float
        ratio: float
        # Outputs aggregated by the post-processor.
        design_results: dict
        tool_calls: list

    react_agent = create_agent(
        model,
        tools=POWER_ANALYSIS_TOOLS,
        state_schema=GraphState,  # type: ignore[arg-type]
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
        logger.info("    * RUN REACT TOOL-CALLING AGENT FOR POWER ANALYSIS")
        logger.info(
            f"    * alpha={state.get('alpha')}, "
            f"power={state.get('power')}, ratio={state.get('ratio')}"
        )
        system_hint = (
            "You are an experiment-design analyst. Follow this playbook:\n"
            "1. If a historical dataset is available, call "
            "   pa_suggest_stratification to identify candidate "
            "   stratification columns.\n"
            "2. To size the experiment, call pa_required_sample_size "
            "   (a priori N) or pa_minimum_detectable_effect "
            "   (sensitivity given a fixed N).\n"
            "3. To translate the sample size into calendar days, call "
            "   pa_estimate_runtime with the daily traffic.\n"
            "4. As a quick one-shot, call pa_design_experiment with the "
            "   metric, baseline, expected lift and traffic.\n"
            "5. Use pa_solve_power only when the user explicitly asks "
            "   for one of the four power-analysis problems beyond "
            "   'size the experiment'.\n"
            "Summarise the recommendation with explicit assumptions "
            "(alpha, power, baseline, expected lift, traffic) and a "
            "confidence-aware caveat ('absolute_lift may be None if "
            "the MDE was too small to invert reliably')."
        )
        base_messages = state.get("messages", []) or [
            ("user", state.get("user_instructions"))  # type: ignore[list-item]
        ]
        messages = [("system", system_hint)] + list(base_messages)  # type: ignore[operator]

        input_payload: Dict[str, Any] = {
            "messages": messages,
            "data_raw": state.get("data_raw") or {},
            "historical_data_raw": state.get("historical_data_raw") or {},
            "alpha": state.get("alpha", alpha),
            "power": state.get("power", power),
            "ratio": state.get("ratio", ratio),
        }
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)  # type: ignore[arg-type]

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING POWER-ANALYSIS RESULTS")

        internal_messages = state.get("messages", []) or []
        if not internal_messages:
            return {"messages": [], "design_results": {}, "tool_calls": []}

        last_ai_message = None
        for msg in reversed(internal_messages):
            role = getattr(msg, "role", None) or getattr(msg, "type", None)
            if role in ("assistant", "ai"):
                last_ai_message = AIMessage(
                    content=getattr(msg, "content", ""),
                    name=AGENT_NAME,
                )
                break
        if last_ai_message is None:
            last_ai_message = AIMessage(
                content=getattr(internal_messages[-1], "content", ""),
                name=AGENT_NAME,
            )
        if not getattr(last_ai_message, "content", "").strip():
            last_ai_message = AIMessage(
                content=("Experiment design ready. See design_results for the per-tool output."),
                name=AGENT_NAME,
            )

        design_artifact: Dict[str, Any] = {
            "solve_power_runs": [],
            "sample_size": None,
            "mde": None,
            "runtime": None,
            "stratification": None,
            "design": None,
        }
        for msg in internal_messages:
            art = getattr(msg, "artifact", None)
            if not isinstance(art, dict):
                continue
            # Route by tool name when known — this is unambiguous because
            # :mod:`langchain_core.messages.ToolMessage` populates ``name``
            # with the tool id (matches the @tool wrapper name).
            tool_name = getattr(msg, "name", None)
            if tool_name == "pa_solve_power":
                design_artifact["solve_power_runs"].append(art)
            elif tool_name == "pa_required_sample_size":
                design_artifact["sample_size"] = art
            elif tool_name == "pa_minimum_detectable_effect":
                design_artifact["mde"] = art
            elif tool_name == "pa_estimate_runtime":
                design_artifact["runtime"] = art
            elif tool_name == "pa_suggest_stratification":
                design_artifact["stratification"] = art
            elif tool_name == "pa_design_experiment":
                design_artifact["design"] = art
            else:
                # Fallback for messages whose ``name`` is unknown (e.g. if
                # a future tool is added without updating this switch):
                # discriminate by shape, but accumulate pa_solve_power
                # runs into the dedicated list to avoid collisions with
                # pa_required_sample_size and pa_minimum_detectable_effect.
                if "solved_value" in art and "solve_for" in art:
                    design_artifact["solve_power_runs"].append(art)
                elif "recommendations" in art:
                    design_artifact["stratification"] = art
                elif "nobs1" in art and "absolute_lift" in art:
                    design_artifact["mde"] = art
                elif "days_needed" in art and "total_required_n" in art:
                    design_artifact["runtime"] = art
                elif "design_inputs" in art and "sample_size" in art:
                    design_artifact["design"] = art
                elif (
                    "solved_value" in art
                    and "metric_type" in art
                    and "alpha" in art
                    and design_artifact["sample_size"] is None
                ):
                    # Best-effort: pa_required_sample_size flat dict.
                    design_artifact["sample_size"] = art

        tool_calls = get_tool_call_names(internal_messages)
        if log_tool_calls and tool_calls:
            for tc in tool_calls:
                logger.info(f"    * Tool: {tc}")

        return {
            "messages": [last_ai_message],
            "internal_messages": internal_messages,
            "design_results": design_artifact,
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

    app = workflow.compile(checkpointer=checkpointer, name=AGENT_NAME)
    return app


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------


class PowerAnalysisAgent(BaseAgent):
    """
    Tool-calling agent that designs experiments end-to-end
    (node type ``experiment.design``).

    Parameters
    ----------
    model : Any
        LangChain LLM (must support tool-calling).
    alpha : float, default 0.05
        Significance level propagated to the tools.
    power : float, default 0.80
        Desired statistical power propagated to the tools.
    ratio : float, default 1.0
        Treatment-to-control sample-size ratio.

    Examples
    --------
    >>> agent = PowerAnalysisAgent(model=llm)
    >>> agent.invoke_agent(
    ...     user_instructions=(
    ...         "Size a +1pp conversion-rate test on 5% baseline, "
    ...         "with 10k daily eligible users."
    ...     )
    ... )
    >>> agent.get_design()
    >>> agent.get_runtime()
    """

    def __init__(
        self,
        model: Any,
        alpha: float = 0.05,
        power: float = 0.80,
        ratio: float = 1.0,
        create_react_agent_kwargs: Optional[Dict] = None,
        invoke_react_agent_kwargs: Optional[Dict] = None,
        checkpointer: Optional[Checkpointer] = None,
        log_tool_calls: bool = True,
    ):
        self._params = {
            "model": model,
            "alpha": alpha,
            "power": power,
            "ratio": ratio,
            "create_react_agent_kwargs": create_react_agent_kwargs or {},
            "invoke_react_agent_kwargs": invoke_react_agent_kwargs or {},
            "checkpointer": checkpointer,
            "log_tool_calls": log_tool_calls,
        }
        self._compiled_graph = self._make_compiled_graph()
        self.response = None

    def _make_compiled_graph(self):
        self.response = None
        return make_power_analysis_agent(**self._params)

    def update_params(self, **kwargs):
        """Updates agent parameters and rebuilds the compiled graph."""
        for k, v in kwargs.items():
            self._params[k] = v
        self._compiled_graph = self._make_compiled_graph()

    def invoke_agent(
        self,
        user_instructions: Optional[str] = None,
        data_raw: Optional[pd.DataFrame] = None,
        historical_data_raw: Optional[pd.DataFrame] = None,
        alpha: Optional[float] = None,
        power: Optional[float] = None,
        ratio: Optional[float] = None,
        **kwargs,
    ):
        """
        Run the experiment-design agent.

        Parameters
        ----------
        user_instructions : str, optional
            Natural-language design goal (e.g. 'Size a +1pp conversion
            test on 5% baseline with 10k daily eligible users').
        data_raw : pd.DataFrame, optional
            Optional dataset injected into state (used by future tools
            that read observations directly; today it is forwarded
            uninterpreted to the agent).
        historical_data_raw : pd.DataFrame, optional
            Optional historical dataset used by
            ``pa_suggest_stratification`` and ``pa_design_experiment``
            to score stratification candidates.
        alpha / power / ratio : optional per-call overrides.
        """
        if user_instructions is None:
            user_instructions = (
                "Design an experiment: choose sample size, expected "
                "runtime and stratification based on the metric baseline "
                "and traffic I will provide. Justify every assumption."
            )

        messages = kwargs.pop("messages", None)
        if messages is None:
            messages = [("user", user_instructions)]

        eff_alpha = alpha if alpha is not None else self._params["alpha"]
        eff_power = power if power is not None else self._params["power"]
        eff_ratio = ratio if ratio is not None else self._params["ratio"]

        response = self._compiled_graph.invoke(
            {
                "messages": messages,
                "user_instructions": user_instructions,
                "data_raw": data_raw.to_dict() if data_raw is not None else {},
                "historical_data_raw": (
                    historical_data_raw.to_dict() if historical_data_raw is not None else {}
                ),
                "alpha": eff_alpha,
                "power": eff_power,
                "ratio": eff_ratio,
            },
            **kwargs,
        )
        self.response = response
        return None

    # ---- Accessors -------------------------------------------------------

    def get_design_results(self) -> Optional[Dict[str, Any]]:
        """Return the full design artifact dict."""
        if not self.response:
            return None
        return self.response.get("design_results")

    def get_sample_size(self) -> Optional[Dict[str, Any]]:
        """Return the most recent ``pa_required_sample_size`` result."""
        r = self.get_design_results() or {}
        return r.get("sample_size")

    def get_mde(self) -> Optional[Dict[str, Any]]:
        """Return the most recent ``pa_minimum_detectable_effect`` result."""
        r = self.get_design_results() or {}
        return r.get("mde")

    def get_runtime(self) -> Optional[Dict[str, Any]]:
        """Return the most recent ``pa_estimate_runtime`` result."""
        r = self.get_design_results() or {}
        return r.get("runtime")

    def get_stratification(self) -> Optional[Dict[str, Any]]:
        """Return the most recent ``pa_suggest_stratification`` result."""
        r = self.get_design_results() or {}
        return r.get("stratification")

    def get_design(self) -> Optional[Dict[str, Any]]:
        """Return the most recent ``pa_design_experiment`` façade result."""
        r = self.get_design_results() or {}
        return r.get("design")

    def get_tool_calls(self) -> Optional[List[str]]:
        """Return the list of tool names that were called."""
        if not self.response:
            return None
        return self.response.get("tool_calls")

    def get_ai_message(self, markdown: bool = False):
        """Return the last AI message from the agent response."""
        if not self.response or "messages" not in self.response:
            return None
        for msg in reversed(self.response.get("messages", [])):
            role = getattr(msg, "role", None) or getattr(msg, "type", None)
            if role in ("assistant", "ai", AGENT_NAME):
                content = getattr(msg, "content", "")
                return Markdown(content) if markdown else content
        return None


__all__ = [
    "AGENT_NAME",
    "NODE_TYPE",
    "PowerAnalysisAgent",
    "make_power_analysis_agent",
    "POWER_ANALYSIS_TOOLS",
    # The 6 individual @tool wrappers — re-exported for registry wiring.
    "pa_solve_power",
    "pa_required_sample_size",
    "pa_minimum_detectable_effect",
    "pa_estimate_runtime",
    "pa_suggest_stratification",
    "pa_design_experiment",
]
