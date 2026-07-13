"""
Tests for ``ai_data_science_team.agents.power_analysis_agent`` (A2 layer).

These tests verify:
* Module-level constants and ``__all__``.
* All six ``@tool`` wrappers are exported with stable names matching
  ``POWER_ANALYSIS_TOOL_NAMES``.
* Direct invocation of ``tool.func(...)`` returns ``(content, artifact)``.
* ``make_power_analysis_agent`` compiles a ``CompiledStateGraph`` with the
  same node wiring as the A1 AB Testing agent.
* ``PowerAnalysisAgent`` (BaseAgent subclass) constructs, exposes accessors,
  rebuilds on ``update_params``, and assembles ``invoke_agent`` payloads
  correctly.

The post-process routing branches are exercised through a synthetic flow
where we drive the agent's compiled graph with messages whose ``artifact``
attribute matches each tool's signature. This is LLM-free: the
``react_agent`` node is replaced with a no-op stub that copies the
synthetic messages into the state.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import pandas as pd
import pytest

# LangChain message primitives — the post-process routing in the agent
# inspects ``msg.artifact`` so we use ToolMessage directly.
from langchain_core.messages import AIMessage, ToolMessage

from ai_data_science_team.agents.power_analysis_agent import (
    AGENT_NAME,
    NODE_TYPE,
    POWER_ANALYSIS_TOOLS,
    PowerAnalysisAgent,
    make_power_analysis_agent,
    pa_design_experiment,
    pa_estimate_runtime,
    pa_minimum_detectable_effect,
    pa_required_sample_size,
    pa_solve_power,
    pa_suggest_stratification,
)


# ---------------------------------------------------------------------------
# Stub model + message helpers
# ---------------------------------------------------------------------------


class _StubModel:
    """A no-op stand-in for a LangChain chat model.

    ``make_power_analysis_agent`` only calls ``create_agent(model, ...)``
    to bind tools; this stub exposes the relevant surface so the factory
    compiles. We never actually drive the LLM in these tests.
    """

    def bind(self, **_):
        return self

    def bind_tools(self, *_args, **_kwargs):
        return self

    def invoke(self, *_args, **_kwargs):
        return AIMessage(content="stub")


def _tool_msg(name: str, artifact: Dict[str, Any]) -> ToolMessage:
    """Build a ToolMessage with the given tool name and artifact payload."""
    return ToolMessage(
        content="",
        tool_call_id="stub",
        name=name,
        artifact=artifact,
    )


def _ai_msg(content: str = "ok") -> AIMessage:
    """Build an AIMessage with the agent's name."""
    return AIMessage(content=content, name=AGENT_NAME)


def _stub_history_df() -> pd.DataFrame:
    import numpy as np

    rng = np.random.RandomState(0)
    n = 600
    return pd.DataFrame(
        {
            "variant": rng.choice(["control", "treatment"], size=n),
            "device": rng.choice(["ios", "android", "web"], size=n),
            "country": rng.choice(["us", "uk", "de", "fr", "tr"], size=n),
            "converted": rng.binomial(1, 0.06, size=n),
        }
    )


def _agent_with_no_op_react() -> PowerAnalysisAgent:
    """
    Build a PowerAnalysisAgent whose compiled graph returns a synthetic
    message history. We achieve this by patching the react_agent node's
    invoke — but a cleaner approach is to monkey-patch the ``react_agent``
    node within the StateGraph before compiling.

    The simplest, model-free path: swap ``create_agent`` with a stub that
    returns an object with an ``invoke`` method honoring the synthetic
    tool results in ``state['messages']``.
    """
    # Use the module's real factory, but make it return a tiny CompiledStateGraph
    # whose ``react_agent`` node is a no-op.  This is achieved by monkeypatching
    # the ``langchain.agents.create_agent`` call to short-circuit.
    from langchain.agents import create_agent as real_create_agent
    from langgraph.graph import END, START, StateGraph
    from langgraph.graph.message import add_messages
    from typing_extensions import Annotated, Sequence, TypedDict
    from langchain_core.messages import BaseMessage

    from ai_data_science_team.agents import power_analysis_agent as pa

    class _GraphState(TypedDict):
        messages: Annotated[Sequence[BaseMessage], add_messages]
        user_instructions: str
        data_raw: dict
        historical_data_raw: dict
        alpha: float
        power: float
        ratio: float
        design_results: dict
        tool_calls: list

    def fake_create_agent(model, tools, **kwargs):
        # Return an object whose invoke forwards to ``state['messages']``
        # unchanged (already pre-populated with tool results by the test).
        from langgraph.prebuilt.chat_agent_executor import (
            CompiledStateGraph as _CompiledStateGraph,
        )

        class _Noop:
            name = "react_agent"

            def invoke(self, payload, config=None, **kwargs):
                # Pass through whatever messages the test put in the
                # state via ``messages`` — post_process reads them.
                return dict(payload)

        return _Noop()

    monkey = pytest.MonkeyPatch()
    monkey.setattr("langchain.agents.create_agent", fake_create_agent)
    agent = PowerAnalysisAgent(model=_StubModel())
    monkey.undo()

    # The agent now uses our patched factory, but the patch was scoped
    # only to the constructor call. We hold onto the agent and let the
    # caller drive it through ``invoke_agent`` (which we then drive
    # directly by populating the response without invoking the graph).
    return agent


# ---------------------------------------------------------------------------
# 1. Module surface
# ---------------------------------------------------------------------------


class TestModuleSurface:
    def test_constants(self):
        assert AGENT_NAME == "power_analysis_agent"
        assert NODE_TYPE == "experiment.design"

    def test_tool_count_matches_registry(self):
        assert len(POWER_ANALYSIS_TOOLS) == 6

    def test_tool_names_match_power_analysis_tool_names(self):
        from ai_data_science_team.tools.power_analysis import (
            POWER_ANALYSIS_TOOL_NAMES,
        )

        names = {t.name for t in POWER_ANALYSIS_TOOLS}
        assert names == set(POWER_ANALYSIS_TOOL_NAMES)

    def test_all_individual_tools_exported(self):
        for fn in (
            pa_solve_power,
            pa_required_sample_size,
            pa_minimum_detectable_effect,
            pa_estimate_runtime,
            pa_suggest_stratification,
            pa_design_experiment,
        ):
            assert hasattr(fn, "name")
            assert hasattr(fn, "invoke")
            assert hasattr(fn, "func")


# ---------------------------------------------------------------------------
# 2. Tool direct invocation (LLM-free)
# ---------------------------------------------------------------------------


class TestPaSolvePower:
    def test_solve_n(self):
        content, art = pa_solve_power.func(
            solve_for="n",
            metric_type="proportion",
            baseline_rate=0.05,
            expected_treatment_rate=0.06,
        )
        assert "pa_solve_power" in content
        assert art["solve_for"] == "n"
        assert art["solved_value"] > 0

    def test_solve_effect_size(self):
        _, art = pa_solve_power.func(
            solve_for="effect_size",
            metric_type="proportion",
            baseline_rate=0.05,
            nobs1=10_000,
        )
        assert art["solve_for"] == "effect_size"
        assert math.isfinite(art["solved_value"])

    def test_solve_power(self):
        _, art = pa_solve_power.func(
            solve_for="power",
            metric_type="proportion",
            baseline_rate=0.05,
            expected_treatment_rate=0.07,
            nobs1=5_000,
        )
        assert 0 <= art["solved_value"] <= 1.0

    def test_solve_alpha(self):
        _, art = pa_solve_power.func(
            solve_for="alpha",
            metric_type="proportion",
            baseline_rate=0.05,
            expected_treatment_rate=0.07,
            nobs1=3_000,
            power=0.80,
        )
        assert 1e-4 < art["solved_value"] < 0.2


class TestPaRequiredSampleSize:
    def test_smoke(self):
        content, art = pa_required_sample_size.func(
            metric_type="proportion",
            baseline_rate=0.05,
            expected_treatment_rate=0.07,
        )
        assert art["solve_for"] == "n"
        assert art["solved_value"] > 0
        assert "Required sample size per arm" in content


class TestPaMinimumDetectableEffect:
    def test_smoke(self):
        content, art = pa_minimum_detectable_effect.func(
            nobs1=10_000,
            metric_type="proportion",
            baseline_rate=0.05,
        )
        assert art["effect_size"] > 0
        assert art["absolute_lift"] is not None
        assert "MDE" in content


class TestPaEstimateRuntime:
    def test_smoke(self):
        content, art = pa_estimate_runtime.func(
            required_n_per_arm=5000,
            daily_traffic=1000,
        )
        assert art["days_needed"] > 0
        assert "Runtime estimate" in content


class TestPaSuggestStratification:
    def test_smoke_with_history(self):
        history = _stub_history_df()
        content, art = pa_suggest_stratification.func(
            data_raw=history.to_dict(),
            group_column="variant",
            max_cardinality=20,
        )
        assert "Stratification" in content
        assert "recommendations" in art
        for r in art["recommendations"]:
            assert r["column"] in history.columns


class TestPaDesignExperiment:
    def test_smoke_full_facade(self):
        history = _stub_history_df()
        content, art = pa_design_experiment.func(
            metric_type="proportion",
            baseline_rate=0.05,
            expected_treatment_rate=0.06,
            daily_traffic=10_000,
            historical_data_raw=history.to_dict(),
            stratification_group_column="variant",
        )
        assert "sample_size" in art
        assert "design_inputs" in art
        assert "runtime" in art
        assert "stratification" in art
        assert "Experiment design ready" in content


# ---------------------------------------------------------------------------
# 3. LangGraph factory
# ---------------------------------------------------------------------------


class TestMakePowerAnalysisAgent:
    def test_compiles_compiled_state_graph(self):
        graph = make_power_analysis_agent(_StubModel(), alpha=0.05, power=0.80)
        assert graph.name == AGENT_NAME
        node_names = set(graph.nodes.keys())
        assert "__start__" in node_names
        assert "prepare_messages" in node_names
        assert "react_agent" in node_names
        assert "post_process" in node_names

    def test_default_kwargs_are_optional(self):
        # All kwargs have defaults — calling with just a model must work.
        graph = make_power_analysis_agent(_StubModel())
        assert graph is not None

    def test_checkpointer_passthrough(self):
        graph = make_power_analysis_agent(_StubModel(), checkpointer=None)
        assert graph is not None


# ---------------------------------------------------------------------------
# 4. PowerAnalysisAgent (BaseAgent subclass) behaviour
# ---------------------------------------------------------------------------


class TestPowerAnalysisAgent:
    def _build(self, **kwargs: Any) -> PowerAnalysisAgent:
        return PowerAnalysisAgent(
            model=_StubModel(),
            alpha=0.05,
            power=0.80,
            ratio=1.0,
            **kwargs,
        )

    def test_is_base_agent(self):
        from ai_data_science_team.templates import BaseAgent

        agent = self._build()
        assert isinstance(agent, BaseAgent)

    def test_update_params_rebuilds_graph(self):
        agent = self._build()
        before = agent._compiled_graph
        agent.update_params(power=0.90)
        after = agent._compiled_graph
        assert before is not after

    def test_invoke_agent_payload(self):
        """``invoke_agent`` must assemble a correct payload structure."""
        agent = self._build()
        captured: Dict[str, Any] = {}

        def _fake_invoke(payload, *_, **__):
            captured["payload"] = payload
            # Simulate a LangGraph response with a synthetic AI message.
            return {
                "messages": [_ai_msg("ok")],
                "design_results": {},
                "tool_calls": [],
            }

        agent._compiled_graph.invoke = _fake_invoke  # type: ignore[assignment]

        history = _stub_history_df()
        agent.invoke_agent(
            user_instructions="Size a +1pp conversion test.",
            historical_data_raw=history,
            alpha=0.01,
        )
        # Response captured.
        assert agent.response["design_results"] == {}
        # Payload:
        assert captured["payload"]["user_instructions"] == (
            "Size a +1pp conversion test."
        )
        assert captured["payload"]["alpha"] == 0.01
        assert captured["payload"]["power"] == 0.80
        assert isinstance(captured["payload"]["historical_data_raw"], dict)
        assert "device" in captured["payload"]["historical_data_raw"]

    def test_default_user_instructions(self):
        agent = self._build()

        def _fake_invoke(payload, *_, **__):
            return {
                "messages": [],
                "user_instructions": payload["user_instructions"],
                "design_results": {},
                "tool_calls": [],
            }

        agent._compiled_graph.invoke = _fake_invoke  # type: ignore[assignment]
        agent.invoke_agent()
        assert "Design an experiment" in agent.response["user_instructions"]

    def test_accessors_with_synthetic_response(self):
        agent = self._build()
        agent.response = {
            "design_results": {
                "sample_size": {"solved_value": 1234, "alpha": 0.05},
                "mde": {"effect_size": 0.04, "absolute_lift": 0.01},
                "runtime": {"days_needed": 10},
                "stratification": {"recommendations": [{"column": "device"}]},
                "design": {
                    "sample_size": {"solved_value": 5678},
                    "design_inputs": {"alpha": 0.05, "power": 0.80},
                    "runtime": {"days_needed": 5},
                },
                "solve_power_runs": [{"solved_value": 0.04}],
            },
            "tool_calls": [
                "pa_required_sample_size",
                "pa_minimum_detectable_effect",
                "pa_estimate_runtime",
                "pa_suggest_stratification",
                "pa_design_experiment",
                "pa_solve_power",
            ],
            "messages": [_ai_msg("hi")],
        }
        assert agent.get_sample_size()["solved_value"] == 1234
        assert agent.get_mde()["absolute_lift"] == 0.01
        assert agent.get_runtime()["days_needed"] == 10
        assert agent.get_stratification()["recommendations"][0]["column"] == "device"
        assert agent.get_design()["sample_size"]["solved_value"] == 5678
        assert agent.get_tool_calls() == [
            "pa_required_sample_size",
            "pa_minimum_detectable_effect",
            "pa_estimate_runtime",
            "pa_suggest_stratification",
            "pa_design_experiment",
            "pa_solve_power",
        ]
        # AI message round-trip.
        assert agent.get_ai_message() == "hi"
        assert agent.get_ai_message(markdown=False) == "hi"


# ---------------------------------------------------------------------------
# 5. Post-processor routing (LLM-free via direct closure call)
# ---------------------------------------------------------------------------


class TestPostProcessRouting:
    """
    The post_process routing decisions depend ONLY on the artifact shape
    inside messages. We exercise the real closure by calling it directly
    with a hand-crafted state dict.

    Strategy:
        Build a CompiledStateGraph, then call the closure stored under
        ``compiled_graph.nodes['post_process']`` with a state that
        contains pre-populated ToolMessage entries.  This bypasses the
        LLM/react_agent entirely while exercising the real routing
        decision logic.
    """

    def _post_process(self):
        agent = PowerAnalysisAgent(model=_StubModel())
        # On a CompiledStateGraph, ``graph.nodes['post_process']`` is a
        # ``PregelNode`` whose ``invoke`` method runs that single node
        # against a state dict.  We invoke it directly with a synthetic
        # ``messages`` payload and inspect the routing output.
        return agent._compiled_graph.nodes["post_process"].invoke

    def _state(self, messages) -> Dict[str, Any]:
        return {"messages": list(messages)}

    def test_sample_size_route(self):
        pp = self._post_process()
        out = pp(self._state([
            _tool_msg(
                "pa_required_sample_size",
                {
                    "solve_for": "n",
                    "solved_value": 5000,
                    "metric_type": "proportion",
                    "alpha": 0.05,
                },
            )
        ]))
        assert out["design_results"]["sample_size"]["solved_value"] == 5000

    def test_mde_route(self):
        pp = self._post_process()
        out = pp(self._state([
            _tool_msg(
                "pa_minimum_detectable_effect",
                {
                    "nobs1": 10_000,
                    "effect_size": 0.04,
                    "absolute_lift": 0.01,
                    "relative_lift": 0.20,
                    "metric_type": "proportion",
                    "alpha": 0.05,
                    "power": 0.80,
                    "ratio": 1.0,
                },
            )
        ]))
        assert out["design_results"]["mde"]["absolute_lift"] == 0.01

    def test_runtime_route(self):
        pp = self._post_process()
        out = pp(self._state([
            _tool_msg(
                "pa_estimate_runtime",
                {"days_needed": 12, "total_required_n": 10_000},
            )
        ]))
        assert out["design_results"]["runtime"]["days_needed"] == 12

    def test_stratification_route(self):
        pp = self._post_process()
        out = pp(self._state([
            _tool_msg(
                "pa_suggest_stratification",
                {"recommendations": [{"column": "device", "score": 1.0}]},
            )
        ]))
        recs = out["design_results"]["stratification"]["recommendations"]
        assert recs and recs[0]["column"] == "device"

    def test_design_facade_route(self):
        pp = self._post_process()
        out = pp(self._state([
            _tool_msg(
                "pa_design_experiment",
                {
                    "sample_size": {"solved_value": 8000},
                    "design_inputs": {"alpha": 0.05, "power": 0.80},
                    "runtime": {"days_needed": 2},
                },
            )
        ]))
        design = out["design_results"]["design"]
        assert design["sample_size"]["solved_value"] == 8000

    def test_solve_power_runs_accumulate(self):
        pp = self._post_process()
        out = pp(self._state([
            _tool_msg(
                "pa_solve_power",
                {
                    "solve_for": "power",
                    "solved_value": 0.65,
                    "alpha": 0.05,
                    "metric_type": "proportion",
                    "nobs1": 5000,
                    "ratio": 1.0,
                    "effect_size": 0.04,
                },
            ),
            _tool_msg(
                "pa_solve_power",
                {
                    "solve_for": "alpha",
                    "solved_value": 0.04,
                    "alpha": 0.04,
                    "metric_type": "continuous",
                    "nobs1": 1000,
                    "ratio": 1.0,
                    "effect_size": 0.10,
                },
            ),
        ]))
        runs = out["design_results"]["solve_power_runs"]
        assert len(runs) == 2

    def test_empty_messages_returns_empty_artifacts(self):
        pp = self._post_process()
        out = pp(self._state([]))
        assert out["design_results"] == {}
        assert out["tool_calls"] == []

    def test_sample_size_vs_solve_power_routing_are_disjoint(self):
        """A pa_required_sample_size artifact must NOT land in solve_power_runs."""
        pp = self._post_process()
        out = pp(self._state([
            _tool_msg(
                "pa_required_sample_size",
                {
                    "solve_for": "n",
                    "solved_value": 8000,
                    "metric_type": "proportion",
                    "alpha": 0.05,
                },
            )
        ]))
        assert out["design_results"]["solve_power_runs"] == []
        assert out["design_results"]["sample_size"]["solved_value"] == 8000


# ---------------------------------------------------------------------------
# 6. End-to-end payload assembly (LLM-free)
# ---------------------------------------------------------------------------


class TestInvokeAgentPayload:
    """Pure payload-shape verification for ``invoke_agent``.

    Patches the compiled graph's ``invoke`` so no LLM is needed.
    """

    def test_default_user_instructions_applied(self):
        agent = PowerAnalysisAgent(model=_StubModel())
        captured: Dict[str, Any] = {}

        def _fake(payload, *_, **__):
            captured["payload"] = payload
            return {"messages": [], "design_results": {}, "tool_calls": []}

        agent._compiled_graph.invoke = _fake  # type: ignore[assignment]
        agent.invoke_agent()
        assert "Design an experiment" in captured["payload"]["user_instructions"]

    def test_history_dataframe_becomes_dict(self):
        agent = PowerAnalysisAgent(model=_StubModel())
        history = _stub_history_df()
        captured: Dict[str, Any] = {}

        def _fake(payload, *_, **__):
            captured["payload"] = payload
            return {"messages": [], "design_results": {}, "tool_calls": []}

        agent._compiled_graph.invoke = _fake  # type: ignore[assignment]
        agent.invoke_agent(user_instructions="hello", historical_data_raw=history)
        assert isinstance(captured["payload"]["historical_data_raw"], dict)
        assert "device" in captured["payload"]["historical_data_raw"]

    def test_per_call_alpha_override_applied(self):
        agent = PowerAnalysisAgent(model=_StubModel())
        captured: Dict[str, Any] = {}

        def _fake(payload, *_, **__):
            captured["payload"] = payload
            return {"messages": [], "design_results": {}, "tool_calls": []}

        agent._compiled_graph.invoke = _fake  # type: ignore[assignment]
        agent.invoke_agent(user_instructions="x", alpha=0.001)
        assert captured["payload"]["alpha"] == 0.001
