"""
ABTestingAgent
==============

End-to-end A/B (and A/B/n) experiment analysis agent implementing spec
**A1** from ``docs/AGENT_SPEC_CATALOG.md``.

Capabilities
------------
- Sample Ratio Mismatch (SRM) detection
- Continuous / proportion metric analysis with auto test selection
  (Welch t-test → Mann–Whitney U when normality fails)
- Lift + confidence intervals (analytical & Wilson)
- Multiple-comparison correction (Bonferroni / Benjamini–Hochberg)
- CUPED variance reduction when a pre-experiment covariate is provided
- Sequential-testing peeking warning (always-valid p-value guard)
- Decision recommendation: ship / iterate / abort / watch

The deterministic statistical core lives in
:mod:`ai_data_science_team.tools.ab_testing` so it can be reused outside
the LangGraph runtime (workflow engine, batch jobs, ad-hoc notebooks).

This module wraps that core in ``@tool``-decorated functions and stitches
them into a LangGraph state graph following the same pattern as
``EDAToolsAgent`` and ``DataQualityAgent``.

Node type
---------
``experiment.analyze``  (matches the catalog spec)
"""

from __future__ import annotations

from typing_extensions import (
    Annotated,
    Any,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    TypedDict,
)

import pandas as pd
from IPython.display import Markdown

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import InjectedState
from langgraph.types import Checkpointer

from ai_data_science_team.templates import BaseAgent
from ai_data_science_team.utils.messages import get_tool_call_names
from ai_data_science_team.utils.regex import format_agent_name

from ai_data_science_team.tools.ab_testing import (
    analyze_continuous_metric,
    analyze_proportion_metric,
    apply_cuped,
    apply_multiple_comparison_correction,
    check_sample_ratio_mismatch,
    detect_sequential_peeking,
    recommend_decision,
)


AGENT_NAME = "ab_testing_agent"
NODE_TYPE = "experiment.analyze"


# ---------------------------------------------------------------------------
# LangChain tool wrappers (LLM-callable surface for the react agent)
# ---------------------------------------------------------------------------


@tool(response_format="content_and_artifact")
def ab_check_srm(
    data_raw: Annotated[dict, InjectedState("data_raw")],
    group_column: Annotated[str, InjectedState("group_column")],
    expected_split: Annotated[Optional[dict], InjectedState("expected_split")] = None,
    alpha: float = 0.001,
) -> Tuple[str, Dict]:
    """
    Tool: ab_check_srm
    Description:
        Runs Sample Ratio Mismatch detection on the experiment data.
        Returns counts per group, chi-square statistic, p-value and a
        boolean ``srm_detected`` flag.

    Parameters (injected from state):
        data_raw        : Experiment dataset as dict.
        group_column    : Column with the variant label.
        expected_split  : Optional expected proportion per variant.
                          If None, equal split is assumed.
        alpha           : Significance level for SRM (default 0.001).
    """
    print("    * Tool: ab_check_srm")

    df = pd.DataFrame(data_raw)
    result = check_sample_ratio_mismatch(
        df,
        group_column=group_column,
        expected_split=expected_split,
        alpha=alpha,
    )
    status = "DETECTED" if result["srm_detected"] else "not detected"
    content = (
        f"SRM check ({status}). "
        f"chi2={result['chi2']:.3f}, p={result['p_value']:.4f}. "
        f"Counts: {result['n_per_group']}."
    )
    return content, result


@tool(response_format="content_and_artifact")
def ab_analyze_continuous(
    data_raw: Annotated[dict, InjectedState("data_raw")],
    group_column: Annotated[str, InjectedState("group_column")],
    metric_column: str,
    control_name: str = "control",
    alpha: float = 0.05,
) -> Tuple[str, Dict]:
    """
    Tool: ab_analyze_continuous
    Description:
        Analyses a continuous metric between control and treatment with
        automatic normality-aware test selection (Welch t-test vs
        Mann–Whitney U). Returns lift, CI, p-value and effect size.

    Parameters (injected from state):
        data_raw      : Experiment dataset as dict.
        group_column  : Column with the variant label.
    Args:
        metric_column : Numeric metric column to analyse.
        control_name  : Label of the control variant (default 'control').
        alpha         : Significance level (default 0.05).
    """
    print("    * Tool: ab_analyze_continuous")

    df = pd.DataFrame(data_raw)
    result = analyze_continuous_metric(
        df,
        group_column=group_column,
        metric_column=metric_column,
        control_name=control_name,
        alpha=alpha,
    )
    lift = result.get("relative_lift")
    lift_str = f"{lift:.2%}" if lift is not None and not (lift != lift) else "n/a"
    content = (
        f"Continuous metric '{metric_column}': "
        f"{result['control_mean']:.4f} → {result['treatment_mean']:.4f} "
        f"(lift {lift_str}, p={result['p_value']:.4f}, "
        f"CI [{result['ci_low']:.4f}, {result['ci_high']:.4f}], "
        f"test={result['test_used']})."
    )
    return content, result


@tool(response_format="content_and_artifact")
def ab_analyze_proportion(
    data_raw: Annotated[dict, InjectedState("data_raw")],
    group_column: Annotated[str, InjectedState("group_column")],
    metric_column: str,
    control_name: str = "control",
    alpha: float = 0.05,
) -> Tuple[str, Dict]:
    """
    Tool: ab_analyze_proportion
    Description:
        Analyses a binary (0/1) metric between control and treatment via a
        two-proportion z-test. Returns lift, Wilson CIs and p-value.

    Parameters (injected from state):
        data_raw      : Experiment dataset as dict.
        group_column  : Column with the variant label.
    Args:
        metric_column : 0/1 metric column to analyse.
        control_name  : Label of the control variant (default 'control').
        alpha         : Significance level (default 0.05).
    """
    print("    * Tool: ab_analyze_proportion")

    df = pd.DataFrame(data_raw)
    result = analyze_proportion_metric(
        df,
        group_column=group_column,
        metric_column=metric_column,
        control_name=control_name,
        alpha=alpha,
    )
    content = (
        f"Proportion metric '{metric_column}': "
        f"{result['control_mean']:.4f} → {result['treatment_mean']:.4f} "
        f"(lift {result['relative_lift']:.2%}, p={result['p_value']:.4f})."
    )
    return content, result


@tool(response_format="content_and_artifact")
def ab_apply_cuped(
    data_raw: Annotated[dict, InjectedState("data_raw")],
    group_column: Annotated[str, InjectedState("group_column")],
    metric_column: str,
    covariate_column: str,
    control_name: str = "control",
) -> Tuple[str, Dict]:
    """
    Tool: ab_apply_cuped
    Description:
        Applies CUPED variance reduction using a pre-experiment covariate.
        Returns theta, raw vs adjusted means and the % variance reduction.
    """
    print("    * Tool: ab_apply_cuped")

    df = pd.DataFrame(data_raw)
    result = apply_cuped(
        df,
        group_column=group_column,
        metric_column=metric_column,
        covariate_column=covariate_column,
        control_name=control_name,
    )
    content = (
        f"CUPED applied with covariate '{covariate_column}' "
        f"(theta={result['theta']:.3f}, "
        f"variance reduction={result['variance_reduction_pct']:.1f}%)."
    )
    return content, result


@tool(response_format="content_and_artifact")
def ab_correct_multiple(
    p_values: List[float],
    method: str = "bh",
    alpha: float = 0.05,
) -> Tuple[str, Dict]:
    """
    Tool: ab_correct_multiple
    Description:
        Adjusts a list of raw p-values for multiple comparisons.

    Args:
        p_values : Raw p-values from each metric test.
        method   : 'bonferroni', 'bh', or 'none'.
        alpha    : Family-wise / FDR level (default 0.05).
    """
    print("    * Tool: ab_correct_multiple")

    result = apply_multiple_comparison_correction(
        p_values=p_values, method=method, alpha=alpha
    )
    content = (
        f"Multiple-comparison correction ({result['method']}): "
        f"adjusted p-values={result['adjusted']}, "
        f"rejected at alpha={alpha}: {result['rejected']}."
    )
    return content, result


@tool(response_format="content_and_artifact")
def ab_detect_peeking(
    sequential_p_values: List[float],
    alpha: float = 0.05,
) -> Tuple[str, Dict]:
    """
    Tool: ab_detect_peeking
    Description:
        Flags naive repeated significance testing (peeking). Provide the
        chronological list of p-values from interim looks.

    Args:
        sequential_p_values : P-values ordered chronologically.
        alpha               : Target Type-I error (default 0.05).
    """
    print("    * Tool: ab_detect_peeking")

    result = detect_sequential_peeking(sequential_p_values, alpha=alpha)
    return result["peeking_warning"], result


@tool(response_format="content_and_artifact")
def ab_recommend_decision(
    metric_result: dict,
    min_detectable_lift: Optional[float] = None,
    power: Optional[float] = None,
    required_sample_ratio: float = 1.0,
) -> Tuple[str, Dict]:
    """
    Tool: ab_recommend_decision
    Description:
        Translates a per-metric analysis result into a ship / iterate /
        abort / watch recommendation with rationale.

    Args:
        metric_result          : Output of ab_analyze_* tool.
        min_detectable_lift    : Relative MDE (e.g. 0.02 = 2%).
        power                  : Achieved statistical power, if known.
        required_sample_ratio  : Observed/required sample ratio.
    """
    print("    * Tool: ab_recommend_decision")

    result = recommend_decision(
        metric_result=metric_result,
        min_detectable_lift=min_detectable_lift,
        power=power,
        required_sample_ratio=required_sample_ratio,
    )
    return result["rationale"], result


AB_TESTING_TOOLS = [
    ab_check_srm,
    ab_analyze_continuous,
    ab_analyze_proportion,
    ab_apply_cuped,
    ab_correct_multiple,
    ab_detect_peeking,
    ab_recommend_decision,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_ab_testing_agent(
    model: Any,
    group_column: str = "group",
    expected_split: Optional[Dict[str, float]] = None,
    alpha: float = 0.05,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    checkpointer: Optional[Checkpointer] = None,
    log_tool_calls: bool = True,
):
    """
    Build the LangGraph StateGraph for the ABTestingAgent.

    Parameters
    ----------
    model : Any
        LangChain LLM supporting tool-calling (e.g. ChatOpenAI).
    group_column : str, default 'group'
        Default variant column injected into state.
    expected_split : dict, optional
        Default expected proportions for SRM.
    alpha : float, default 0.05
        Default significance level.
    """
    if create_react_agent_kwargs is None:
        create_react_agent_kwargs = {}
    if invoke_react_agent_kwargs is None:
        invoke_react_agent_kwargs = {}

    class GraphState(TypedDict):
        messages: Annotated[Sequence[BaseMessage], add_messages]
        user_instructions: str
        data_raw: dict
        group_column: str
        expected_split: Optional[dict]
        alpha: float
        analysis_results: dict
        tool_calls: list

    react_agent = create_agent(
        model,
        tools=AB_TESTING_TOOLS,
        state_schema=GraphState,  # type: ignore[arg-type]
        checkpointer=checkpointer,
        **create_react_agent_kwargs,
    )

    def prepare_messages(state: GraphState):
        print(format_agent_name(AGENT_NAME))
        print("    * PREPARE MESSAGES")
        if state.get("messages"):
            return {}
        return {"messages": [("user", state.get("user_instructions"))]}

    def run_react_agent(state: GraphState):
        print("    * RUN REACT TOOL-CALLING AGENT FOR A/B TESTING")
        print(
            f"    * group_column={state.get('group_column')}, "
            f"alpha={state.get('alpha')}"
        )
        system_hint = (
            "You are an A/B testing analyst. Follow this playbook:\n"
            "1. Call ab_check_srm on the experiment data.\n"
            "2. For each metric, call ab_analyze_continuous or "
            "   ab_analyze_proportion as appropriate.\n"
            "3. If multiple metrics were tested, call ab_correct_multiple.\n"
            "4. If a covariate column is available, call ab_apply_cuped for "
            "   the primary metric.\n"
            "5. If interim looks were performed, call ab_detect_peeking.\n"
            "6. Call ab_recommend_decision for the primary metric and "
            "   summarise ship / iterate / abort with rationale.\n"
            "If SRM is detected, stop and warn the user."
        )
        base_messages = state.get("messages", []) or [
            ("user", state.get("user_instructions"))  # type: ignore[list-item]
        ]
        messages = [("system", system_hint)] + list(base_messages)  # type: ignore[operator]

        input_payload = {
            "messages": messages,
            "data_raw": state.get("data_raw"),
            "group_column": state.get("group_column", group_column),
            "expected_split": state.get("expected_split")
            if state.get("expected_split") is not None
            else expected_split,
            "alpha": state.get("alpha", alpha),
        }
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)  # type: ignore[arg-type]

    def post_process(state: GraphState):
        print("    * POST-PROCESSING A/B TESTING RESULTS")

        internal_messages = state.get("messages", []) or []
        if not internal_messages:
            return {"messages": [], "analysis_results": {}, "tool_calls": []}

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
                content=(
                    "A/B testing analysis complete. "
                    "See analysis_results for the detailed per-metric output."
                ),
                name=AGENT_NAME,
            )

        analysis_artifact: Dict[str, Any] = {
            "srm": None,
            "metrics": [],
            "cuped": None,
            "multiple_comparison": None,
            "peeking": None,
            "decision": None,
        }
        for msg in internal_messages:
            art = getattr(msg, "artifact", None)
            if not isinstance(art, dict):
                continue
            if "srm_detected" in art:
                analysis_artifact["srm"] = art
            elif "variance_reduction_pct" in art:
                analysis_artifact["cuped"] = art
            elif "adjusted" in art and "rejected" in art and len(art.get("adjusted", [])) > 1:
                analysis_artifact["multiple_comparison"] = art
            elif "n_looks" in art:
                analysis_artifact["peeking"] = art
            elif "decision" in art and "rationale" in art:
                analysis_artifact["decision"] = art
            elif "metric_type" in art:
                analysis_artifact["metrics"].append(art)

        tool_calls = get_tool_call_names(internal_messages)
        if log_tool_calls and tool_calls:
            for tc in tool_calls:
                print(f"    * Tool: {tc}")

        return {
            "messages": [last_ai_message],
            "internal_messages": internal_messages,
            "analysis_results": analysis_artifact,
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


class ABTestingAgent(BaseAgent):
    """
    Tool-calling agent that performs end-to-end A/B test analysis
    (node type ``experiment.analyze``).

    Parameters
    ----------
    model : Any
        LangChain LLM (must support tool-calling).
    group_column : str, default 'group'
        Variant column in the experiment data.
    expected_split : dict, optional
        Expected proportions per variant. ``None`` → equal split.
    alpha : float, default 0.05
        Significance level.

    Examples
    --------
    >>> agent = ABTestingAgent(model=llm)
    >>> agent.invoke_agent(
    ...     data_raw=df,
    ...     user_instructions="Analyse the conversion experiment."
    ... )
    >>> agent.get_analysis_results()
    """

    def __init__(
        self,
        model: Any,
        group_column: str = "group",
        expected_split: Optional[Dict[str, float]] = None,
        alpha: float = 0.05,
        create_react_agent_kwargs: Optional[Dict] = None,
        invoke_react_agent_kwargs: Optional[Dict] = None,
        checkpointer: Optional[Checkpointer] = None,
        log_tool_calls: bool = True,
    ):
        self._params = {
            "model": model,
            "group_column": group_column,
            "expected_split": expected_split,
            "alpha": alpha,
            "create_react_agent_kwargs": create_react_agent_kwargs or {},
            "invoke_react_agent_kwargs": invoke_react_agent_kwargs or {},
            "checkpointer": checkpointer,
            "log_tool_calls": log_tool_calls,
        }
        self._compiled_graph = self._make_compiled_graph()
        self.response = None

    def _make_compiled_graph(self):
        self.response = None
        return make_ab_testing_agent(**self._params)

    def update_params(self, **kwargs):
        """Updates agent parameters and rebuilds the compiled graph."""
        for k, v in kwargs.items():
            self._params[k] = v
        self._compiled_graph = self._make_compiled_graph()

    def invoke_agent(
        self,
        data_raw: pd.DataFrame,
        user_instructions: Optional[str] = None,
        group_column: Optional[str] = None,
        expected_split: Optional[Dict[str, float]] = None,
        alpha: Optional[float] = None,
        **kwargs,
    ):
        """
        Run the A/B testing analysis on ``data_raw``.

        Parameters
        ----------
        data_raw : pd.DataFrame
            Experiment dataset.
        user_instructions : str, optional
            Natural-language goal (e.g. 'Analyse the conversion test').
        group_column / expected_split / alpha : optional overrides for this call.
        """
        if user_instructions is None:
            user_instructions = (
                "Analyse this A/B experiment end-to-end: check SRM, run the "
                "appropriate metric test(s), apply multiple-comparison correction "
                "if needed, optionally apply CUPED, and recommend a decision."
            )

        messages = kwargs.pop("messages", None)
        if messages is None:
            messages = [("user", user_instructions)]

        eff_group = group_column or self._params["group_column"]
        eff_split = (
            expected_split if expected_split is not None
            else self._params.get("expected_split")
        )
        eff_alpha = alpha if alpha is not None else self._params["alpha"]

        response = self._compiled_graph.invoke(
            {
                "messages": messages,
                "user_instructions": user_instructions,
                "data_raw": data_raw.to_dict() if data_raw is not None else {},
                "group_column": eff_group,
                "expected_split": eff_split,
                "alpha": eff_alpha,
            },
            **kwargs,
        )
        self.response = response
        return None

    # ---- Accessors -------------------------------------------------------

    def get_analysis_results(self) -> Optional[Dict[str, Any]]:
        """Return the full analysis artifact dict."""
        if not self.response:
            return None
        return self.response.get("analysis_results")

    def get_srm(self) -> Optional[Dict[str, Any]]:
        """Return SRM check result (or None if not run)."""
        r = self.get_analysis_results() or {}
        return r.get("srm")

    def get_metric_results(self) -> Optional[List[Dict[str, Any]]]:
        """Return the list of per-metric analysis results."""
        r = self.get_analysis_results() or {}
        return r.get("metrics")

    def get_cuped(self) -> Optional[Dict[str, Any]]:
        """Return CUPED result (or None if not run)."""
        r = self.get_analysis_results() or {}
        return r.get("cuped")

    def get_multiple_comparison(self) -> Optional[Dict[str, Any]]:
        """Return multiple-comparison correction result (or None if not run)."""
        r = self.get_analysis_results() or {}
        return r.get("multiple_comparison")

    def get_peeking(self) -> Optional[Dict[str, Any]]:
        """Return sequential-testing peeking result (or None if not run)."""
        r = self.get_analysis_results() or {}
        return r.get("peeking")

    def get_decision(self) -> Optional[Dict[str, Any]]:
        """Return final ship/iterate/abort/watch recommendation."""
        r = self.get_analysis_results() or {}
        return r.get("decision")

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
    "ABTestingAgent",
    "make_ab_testing_agent",
    "AB_TESTING_TOOLS",
]
