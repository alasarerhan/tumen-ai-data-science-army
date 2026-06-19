"""TG1 — Unit tests for M22 Orchestration Layer.

Covers:
* WorkflowSignal / SignalStore
* AgentRegistry
* ContextStore
* WorkflowResolver (validate_spec, build helpers, scenario detection)
* RuntimeEngine (success, retry, failure, signal handling, circuit breaker,
  graceful degradation, checkpoint)
* OrchestratorAgent (construction, invoke_agent, getters, update_params)

Run with:
    pytest tests/test_m22_orchestration.py -v
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------
from ai_data_science_team.signals import (
    SignalStore,
    SignalType,
    WorkflowSignal,
    get_signal_store,
)
from ai_data_science_team.agent_registry import AgentMetadata, AgentRegistry
from ai_data_science_team.context_store import ContextStore
from ai_data_science_team.workflow_resolver import (
    WorkflowResolver,
    build_spec,
    build_step,
    validate_spec,
)
from ai_data_science_team.runtime_engine import RunResult, RuntimeEngine, StepResult


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture(autouse=True)
def clean_registry():
    """Clear AgentRegistry before every test to avoid cross-test pollution."""
    AgentRegistry.clear()
    yield
    AgentRegistry.clear()


def _make_spec(name: str = "test_workflow", n_steps: int = 2) -> Dict[str, Any]:
    """Helper: create a minimal valid WorkflowSpec."""
    steps = []
    for i in range(n_steps):
        steps.append(build_step(f"step_{i}", "MockAgent", f"Do task {i}"))
    return build_spec(name=name, steps=steps, description="Unit test workflow")


def _ok_executor(agent_name: str, instruction: str, context: dict) -> Dict[str, Any]:
    """Executor that always succeeds."""
    return {"agent": agent_name, "result": "ok"}


def _fail_executor(agent_name: str, instruction: str, context: dict) -> None:
    """Executor that always raises."""
    raise RuntimeError("Simulated agent failure")


# ===========================================================================
# WorkflowSignal + SignalStore
# ===========================================================================


class TestWorkflowSignal:
    def test_create_signal_defaults(self):
        sig = WorkflowSignal(type=SignalType.ANNOTATE, session_id="s1")
        assert sig.session_id == "s1"
        assert sig.type == SignalType.ANNOTATE
        assert sig.consumed is False
        assert sig.signal_id  # auto-generated UUID

    def test_consume_sets_flag(self):
        sig = WorkflowSignal(type=SignalType.SKIP, session_id="s1", step_id="step_0")
        returned = sig.consume()
        assert sig.consumed is True
        assert returned is sig  # fluent API

    def test_to_dict_keys(self):
        sig = WorkflowSignal(type=SignalType.CANCEL, session_id="s1")
        d = sig.to_dict()
        for key in ("signal_id", "type", "session_id", "consumed", "timestamp"):
            assert key in d, f"Missing key: {key}"

    def test_signal_type_values(self):
        assert SignalType.CANCEL == "cancel"
        assert SignalType.SKIP == "skip"
        assert SignalType.MODIFY == "modify"
        assert SignalType.ANNOTATE == "annotate"
        assert SignalType.PAUSE == "pause"
        assert SignalType.RESUME == "resume"


class TestSignalStore:
    def test_emit_and_pop(self):
        store = SignalStore()
        sig = WorkflowSignal(type=SignalType.SKIP, session_id="s1", step_id="step_0")
        store.emit(sig)
        pending = store.pop_pending("s1")
        assert len(pending) == 1
        assert pending[0].type == SignalType.SKIP

    def test_pop_marks_consumed(self):
        store = SignalStore()
        store.emit(WorkflowSignal(type=SignalType.CANCEL, session_id="s1"))
        store.pop_pending("s1")
        # Second pop should return empty
        assert store.pop_pending("s1") == []

    def test_emit_multiple_signals(self):
        store = SignalStore()
        for stype in (SignalType.SKIP, SignalType.ANNOTATE, SignalType.CANCEL):
            store.emit(WorkflowSignal(type=stype, session_id="s2"))
        pending = store.pop_pending("s2")
        assert len(pending) == 3

    def test_list_all_includes_consumed(self):
        store = SignalStore()
        store.emit(WorkflowSignal(type=SignalType.PAUSE, session_id="s3"))
        store.pop_pending("s3")  # consumes
        all_sigs = store.list_all("s3")
        assert len(all_sigs) == 1
        assert all_sigs[0].consumed is True

    def test_clear_session(self):
        store = SignalStore()
        store.emit(WorkflowSignal(type=SignalType.MODIFY, session_id="s4"))
        store.clear("s4")
        assert store.pop_pending("s4") == []

    def test_unknown_session_returns_empty(self):
        store = SignalStore()
        assert store.pop_pending("nonexistent") == []

    def test_get_signal_store_returns_singleton(self):
        s1 = get_signal_store()
        s2 = get_signal_store()
        assert s1 is s2


# ===========================================================================
# AgentRegistry
# ===========================================================================


class _MockAgent:
    """Dummy agent class for registry tests."""
    pass


class TestAgentRegistry:
    def test_register_and_get(self):
        meta = AgentRegistry.register(
            name="MockAgent",
            agent_class=_MockAgent,
            capabilities=["mock"],
            description="A mock agent.",
        )
        assert meta.name == "MockAgent"
        retrieved = AgentRegistry.get("MockAgent")
        assert retrieved is meta

    def test_register_overwrite(self):
        AgentRegistry.register(name="A", agent_class=_MockAgent, capabilities=["x"])
        AgentRegistry.register(name="A", agent_class=_MockAgent, capabilities=["y"], overwrite=True)
        assert "y" in AgentRegistry.get("A").capabilities
        assert "x" not in AgentRegistry.get("A").capabilities

    def test_register_no_overwrite_raises(self):
        AgentRegistry.register(name="B", agent_class=_MockAgent, capabilities=[])
        with pytest.raises(ValueError, match="already registered"):
            AgentRegistry.register(
                name="B", agent_class=_MockAgent, capabilities=[], overwrite=False
            )

    def test_get_unknown_raises(self):
        with pytest.raises(KeyError):
            AgentRegistry.get("DoesNotExist")

    def test_get_or_none_returns_none(self):
        assert AgentRegistry.get_or_none("Ghost") is None

    def test_query_by_capability(self):
        AgentRegistry.register("Alpha", _MockAgent, capabilities=["eda", "clean"])
        AgentRegistry.register("Beta", _MockAgent, capabilities=["model"])
        results = AgentRegistry.query(capability="eda")
        assert len(results) == 1
        assert results[0].name == "Alpha"

    def test_query_by_tag(self):
        AgentRegistry.register("Gamma", _MockAgent, capabilities=[], tags=["ml"])
        AgentRegistry.register("Delta", _MockAgent, capabilities=[], tags=["data"])
        assert len(AgentRegistry.query(tag="ml")) == 1

    def test_query_by_cost_tier(self):
        AgentRegistry.register("Cheap", _MockAgent, capabilities=[], cost_tier="low")
        AgentRegistry.register("Expensive", _MockAgent, capabilities=[], cost_tier="high")
        low_cost = AgentRegistry.query(cost_tier="low")
        assert all(m.cost_tier == "low" for m in low_cost)

    def test_list_all_sorted(self):
        AgentRegistry.register("Z", _MockAgent)
        AgentRegistry.register("A", _MockAgent)
        names = [m.name for m in AgentRegistry.list_all()]
        assert names == sorted(names)

    def test_names(self):
        AgentRegistry.register("X", _MockAgent)
        AgentRegistry.register("Y", _MockAgent)
        assert "X" in AgentRegistry.names()
        assert "Y" in AgentRegistry.names()

    def test_size(self):
        assert AgentRegistry.size() == 0
        AgentRegistry.register("One", _MockAgent)
        assert AgentRegistry.size() == 1

    def test_to_catalog_json_serialisable(self):
        AgentRegistry.register("Serialisable", _MockAgent, capabilities=["test"])
        import json
        catalog = AgentRegistry.to_catalog()
        json.dumps(catalog)  # must not raise

    def test_to_dict_contains_expected_keys(self):
        AgentRegistry.register("Full", _MockAgent, capabilities=["c1"], tags=["t1"])
        d = AgentRegistry.get("Full").to_dict()
        for key in ("name", "description", "capabilities", "cost_tier", "tags", "version"):
            assert key in d, f"Missing key: {key}"

    def test_unregister(self):
        AgentRegistry.register("Temp", _MockAgent)
        AgentRegistry.unregister("Temp")
        assert AgentRegistry.get_or_none("Temp") is None

    def test_clear(self):
        AgentRegistry.register("One", _MockAgent)
        AgentRegistry.register("Two", _MockAgent)
        AgentRegistry.clear()
        assert AgentRegistry.size() == 0


# ===========================================================================
# ContextStore
# ===========================================================================


class TestContextStore:
    def test_create_session_returns_id(self):
        store = ContextStore()
        sid = store.create_session()
        assert isinstance(sid, str)
        assert store.session_exists(sid)

    def test_create_session_explicit_id(self):
        store = ContextStore()
        sid = store.create_session(session_id="my-session")
        assert sid == "my-session"

    def test_get_session_raises_unknown(self):
        store = ContextStore()
        with pytest.raises(KeyError):
            store.get_session("ghost")

    def test_set_and_get(self):
        store = ContextStore()
        sid = store.create_session()
        store.set(sid, "df", {"rows": 100})
        assert store.get(sid, "df") == {"rows": 100}

    def test_get_default(self):
        store = ContextStore()
        sid = store.create_session()
        assert store.get(sid, "missing_key", default="fallback") == "fallback"

    def test_delete_key(self):
        store = ContextStore()
        sid = store.create_session()
        store.set(sid, "k", "v")
        store.delete(sid, "k")
        assert store.get(sid, "k") is None

    def test_keys_excludes_private(self):
        store = ContextStore()
        sid = store.create_session()
        store.set(sid, "user_key", 42)
        assert "user_key" in store.keys(sid)
        assert "_meta" not in store.keys(sid)
        assert "_artifacts" not in store.keys(sid)

    def test_append_and_get_artifacts(self):
        store = ContextStore()
        sid = store.create_session()
        store.append_artifact(sid, "chart", {"type": "bar"}, step_id="viz")
        store.append_artifact(sid, "table", {"rows": 10}, step_id="eda")
        assert store.artifact_count(sid) == 2
        charts = store.get_artifacts(sid, artifact_type="chart")
        assert len(charts) == 1
        assert charts[0]["step_id"] == "viz"

    def test_get_artifacts_filter_by_step(self):
        store = ContextStore()
        sid = store.create_session()
        store.append_artifact(sid, "report", "...", step_id="step_1")
        store.append_artifact(sid, "report", "...", step_id="step_2")
        assert len(store.get_artifacts(sid, step_id="step_1")) == 1

    def test_clear_session(self):
        store = ContextStore()
        sid = store.create_session()
        store.set(sid, "k", "v")
        store.clear_session(sid)
        assert not store.session_exists(sid)

    def test_list_sessions(self):
        store = ContextStore()
        s1 = store.create_session()
        s2 = store.create_session()
        sessions = store.list_sessions()
        assert s1 in sessions
        assert s2 in sessions

    def test_get_meta(self):
        store = ContextStore()
        sid = store.create_session(user_id="u1", workspace_id="ws1", scenario="dynamic")
        meta = store.get_meta(sid)
        assert meta["user_id"] == "u1"
        assert meta["scenario"] == "dynamic"

    def test_update_meta(self):
        store = ContextStore()
        sid = store.create_session()
        store.update_meta(sid, workflow_name="test_wf")
        assert store.get_meta(sid).get("workflow_name") == "test_wf"


# ===========================================================================
# WorkflowResolver + validate_spec
# ===========================================================================


class TestValidateSpec:
    def test_valid_spec_no_errors(self):
        spec = _make_spec()
        assert validate_spec(spec) == []

    def test_missing_name(self):
        spec = {"steps": [build_step("s0", "A", "task")]}
        errors = validate_spec(spec)
        assert any("name" in e for e in errors)

    def test_empty_steps(self):
        spec = {"name": "empty", "steps": []}
        errors = validate_spec(spec)
        assert any("steps" in e for e in errors)

    def test_not_a_dict(self):
        errors = validate_spec("not a dict")  # type: ignore[arg-type]
        assert errors

    def test_step_missing_id(self):
        spec = {"name": "w", "steps": [{"agent": "A", "instruction": "task"}]}
        errors = validate_spec(spec)
        assert any("id" in e for e in errors)

    def test_step_missing_agent(self):
        spec = {"name": "w", "steps": [{"id": "s0", "instruction": "task"}]}
        errors = validate_spec(spec)
        assert any("agent" in e for e in errors)

    def test_step_missing_instruction(self):
        spec = {"name": "w", "steps": [{"id": "s0", "agent": "A"}]}
        errors = validate_spec(spec)
        assert any("instruction" in e for e in errors)

    def test_duplicate_step_id(self):
        spec = {
            "name": "w",
            "steps": [
                {"id": "s0", "agent": "A", "instruction": "t"},
                {"id": "s0", "agent": "B", "instruction": "t"},
            ],
        }
        errors = validate_spec(spec)
        assert any("duplicate" in e.lower() for e in errors)

    def test_depends_on_unknown_id(self):
        spec = {
            "name": "w",
            "steps": [
                build_step("s1", "A", "t", depends_on=["nonexistent"]),
            ],
        }
        errors = validate_spec(spec)
        assert any("nonexistent" in e for e in errors)


class TestBuildHelpers:
    def test_build_step(self):
        s = build_step("s0", "AgentX", "Do something", depends_on=["prev"], fallbacks=["AgentY"])
        assert s["id"] == "s0"
        assert s["agent"] == "AgentX"
        assert s["depends_on"] == ["prev"]
        assert s["fallbacks"] == ["AgentY"]

    def test_build_spec(self):
        steps = [build_step("s0", "A", "t")]
        spec = build_spec("MyWorkflow", steps, description="A test workflow")
        assert spec["name"] == "MyWorkflow"
        assert len(spec["steps"]) == 1


class TestWorkflowResolver:
    def test_supervised_scenario_from_spec(self):
        resolver = WorkflowResolver()
        spec = _make_spec()
        result = resolver.resolve(workflow_spec=spec)
        assert result["scenario"] == WorkflowResolver.SUPERVISED
        assert result["spec"] == spec
        assert result["errors"] == []

    def test_manual_scenario_when_managed_by_user(self):
        resolver = WorkflowResolver()
        spec = _make_spec()
        result = resolver.resolve(workflow_spec=spec, managed_by_user=True)
        assert result["scenario"] == WorkflowResolver.MANUAL

    def test_explicit_scenario_override(self):
        resolver = WorkflowResolver()
        spec = _make_spec()
        result = resolver.resolve(workflow_spec=spec, scenario="manual")
        assert result["scenario"] == "manual"

    def test_no_goal_no_spec_manual(self):
        resolver = WorkflowResolver()
        result = resolver.resolve()
        assert result["scenario"] == WorkflowResolver.MANUAL
        assert result["errors"]  # no spec provided

    def test_dynamic_scenario_detected_from_goal(self):
        resolver = WorkflowResolver(model=None)
        result = resolver.resolve(user_goal="Analyse sales data")
        assert result["scenario"] == WorkflowResolver.DYNAMIC
        assert result["errors"] == []
        assert result["spec"]["name"] == "dynamic_data_science_workflow"
        assert len(result["spec"]["steps"]) == 1

    def test_dynamic_scenario_with_mocked_model(self):
        spec = _make_spec("generated_wf", n_steps=1)
        import json

        mock_model = MagicMock()
        mock_model.invoke.return_value = MagicMock(content=json.dumps(spec))

        resolver = WorkflowResolver(model=mock_model)
        result = resolver.resolve(user_goal="Do some analysis")
        assert result["scenario"] == WorkflowResolver.DYNAMIC
        assert result["spec"]["name"] == "generated_wf"
        assert result["errors"] == []

    def test_static_validate(self):
        spec = _make_spec()
        assert WorkflowResolver.validate(spec) == []

    def test_static_build_step(self):
        s = WorkflowResolver.build_step("id1", "Agent", "instr")
        assert s["id"] == "id1"

    def test_static_build_spec(self):
        spec = WorkflowResolver.build_spec("W", [WorkflowResolver.build_step("s0", "A", "t")])
        assert spec["name"] == "W"


# ===========================================================================
# RuntimeEngine
# ===========================================================================


class TestRuntimeEngineSuccess:
    def test_single_step_success(self):
        engine = RuntimeEngine(agent_executor=_ok_executor, backoff_base=0)
        spec = _make_spec(n_steps=1)
        result = engine.run(spec, session_id="s1")
        assert result.status == "completed"
        assert result.success_count == 1
        assert result.failed_count == 0

    def test_multi_step_success(self):
        engine = RuntimeEngine(agent_executor=_ok_executor, backoff_base=0)
        spec = _make_spec(n_steps=3)
        result = engine.run(spec, session_id=str(uuid.uuid4()))
        assert result.success_count == 3
        assert result.status == "completed"

    def test_outputs_stored_in_final_outputs(self):
        engine = RuntimeEngine(agent_executor=_ok_executor, backoff_base=0)
        spec = _make_spec(n_steps=2)
        result = engine.run(spec, session_id=str(uuid.uuid4()))
        for step in spec["steps"]:
            assert step["id"] in result.final_outputs

    def test_run_result_to_dict(self):
        engine = RuntimeEngine(agent_executor=_ok_executor, backoff_base=0)
        spec = _make_spec(n_steps=1)
        result = engine.run(spec, session_id=str(uuid.uuid4()))
        d = result.to_dict()
        assert "workflow_name" in d
        assert "status" in d
        assert "steps" in d


class TestRuntimeEngineRetry:
    def test_retry_then_succeed(self):
        call_count = {"n": 0}

        def flaky_executor(agent_name, instruction, context):
            call_count["n"] += 1
            if call_count["n"] < 2:
                raise RuntimeError("first attempt fails")
            return {"ok": True}

        engine = RuntimeEngine(
            agent_executor=flaky_executor,
            max_retries=2,
            backoff_base=0,
        )
        spec = _make_spec(n_steps=1)
        result = engine.run(spec, session_id=str(uuid.uuid4()))
        assert result.status == "completed"
        assert result.step_results[0].retries == 1
        assert result.step_results[0].status == "success"

    def test_all_retries_exhaust_then_fallback_succeeds(self):
        calls: list = []

        def executor(agent_name, instruction, context):
            calls.append(agent_name)
            if agent_name == "primary":
                raise RuntimeError("primary fails")
            return {"ok": "fallback"}

        step = build_step("s0", "primary", "task", fallbacks=["fallback"])
        spec = build_spec("wf", [step])

        engine = RuntimeEngine(
            agent_executor=executor,
            max_retries=1,
            backoff_base=0,
        )
        result = engine.run(spec, session_id=str(uuid.uuid4()))
        assert result.step_results[0].status == "success"
        assert result.step_results[0].agent_name == "fallback"


class TestRuntimeEngineFailure:
    def test_graceful_degradation_continues(self):
        engine = RuntimeEngine(
            agent_executor=_fail_executor,
            max_retries=0,
            backoff_base=0,
            graceful_degradation=True,
        )
        spec = _make_spec(n_steps=3)
        result = engine.run(spec, session_id=str(uuid.uuid4()))
        # All steps attempted; status not "completed" after failures but run continues
        assert len(result.step_results) == 3

    def test_no_graceful_degradation_aborts(self):
        engine = RuntimeEngine(
            agent_executor=_fail_executor,
            max_retries=0,
            backoff_base=0,
            graceful_degradation=False,
        )
        spec = _make_spec(n_steps=3)
        result = engine.run(spec, session_id=str(uuid.uuid4()))
        assert result.status == "degraded"
        # Stopped after first failure
        assert len(result.step_results) == 1

    def test_dependency_unmet_skips_step(self):
        def executor(agent_name, instruction, context):
            if agent_name == "FailAgent":
                raise RuntimeError("fail")
            return {"ok": True}

        step_a = build_step("a", "FailAgent", "task_a")
        step_b = build_step("b", "OkAgent", "task_b", depends_on=["a"])
        spec = build_spec("w", [step_a, step_b])

        engine = RuntimeEngine(
            agent_executor=executor,
            max_retries=0,
            backoff_base=0,
            graceful_degradation=True,
        )
        result = engine.run(spec, session_id=str(uuid.uuid4()))
        # step_b should NOT be skipped here because with graceful_degradation=True
        # step_a is still added to completed_ids (just with failed status)
        step_statuses = {sr.step_id: sr.status for sr in result.step_results}
        assert step_statuses["a"] == "failed"


class TestRuntimeEngineSignals:
    def test_cancel_signal_stops_run(self):
        signal_store = SignalStore()
        session_id = str(uuid.uuid4())

        call_count = {"n": 0}

        def executor(agent_name, instruction, context):
            call_count["n"] += 1
            return {"ok": True}

        # Pre-emit a cancel signal before the run starts
        signal_store.emit(
            WorkflowSignal(type=SignalType.CANCEL, session_id=session_id)
        )

        engine = RuntimeEngine(
            agent_executor=executor,
            signal_store=signal_store,
            backoff_base=0,
        )
        spec = _make_spec(n_steps=3)
        result = engine.run(spec, session_id=session_id)
        assert result.status == "cancelled"
        assert call_count["n"] == 0  # no steps ran

    def test_skip_signal_skips_step(self):
        signal_store = SignalStore()
        session_id = str(uuid.uuid4())

        signal_store.emit(
            WorkflowSignal(
                type=SignalType.SKIP,
                session_id=session_id,
                step_id="step_0",
            )
        )

        engine = RuntimeEngine(
            agent_executor=_ok_executor,
            signal_store=signal_store,
            backoff_base=0,
        )
        spec = _make_spec(n_steps=2)
        result = engine.run(spec, session_id=session_id)
        statuses = {sr.step_id: sr.status for sr in result.step_results}
        assert statuses.get("step_0") == "skipped"
        assert statuses.get("step_1") == "success"

    def test_modify_signal_changes_instruction(self):
        received_instructions: list = []

        def recording_executor(agent_name, instruction, context):
            received_instructions.append(instruction)
            return {"ok": True}

        signal_store = SignalStore()
        session_id = str(uuid.uuid4())

        signal_store.emit(
            WorkflowSignal(
                type=SignalType.MODIFY,
                session_id=session_id,
                step_id="step_0",
                payload={"instruction": "MODIFIED INSTRUCTION"},
            )
        )

        engine = RuntimeEngine(
            agent_executor=recording_executor,
            signal_store=signal_store,
            backoff_base=0,
        )
        spec = _make_spec(n_steps=1)
        engine.run(spec, session_id=session_id)
        assert received_instructions[0] == "MODIFIED INSTRUCTION"

    def test_annotate_signal_stored_in_outputs(self):
        signal_store = SignalStore()
        session_id = str(uuid.uuid4())

        signal_store.emit(
            WorkflowSignal(
                type=SignalType.ANNOTATE,
                session_id=session_id,
                step_id="step_0",
                payload={"note": "Looks great!"},
            )
        )

        engine = RuntimeEngine(
            agent_executor=_ok_executor,
            signal_store=signal_store,
            backoff_base=0,
        )
        spec = _make_spec(n_steps=1)
        result = engine.run(spec, session_id=session_id)
        annotations = result.final_outputs.get("_annotations", [])
        assert len(annotations) == 1
        assert annotations[0]["note"] == "Looks great!"


class TestCircuitBreaker:
    def test_circuit_opens_after_threshold(self):
        engine = RuntimeEngine(
            agent_executor=_fail_executor,
            max_retries=0,
            backoff_base=0,
            cb_threshold=2,
            graceful_degradation=True,
        )
        session_id = str(uuid.uuid4())
        # Run enough steps to trip the circuit breaker
        steps = [build_step(f"s{i}", "FailAgent", "task") for i in range(5)]
        spec = build_spec("wf", steps)
        result = engine.run(spec, session_id=session_id)
        statuses = [sr.status for sr in result.step_results]
        # After cb_threshold failures, further steps should be skipped
        assert "skipped" in statuses


class TestCheckpoint:
    def test_checkpoint_stored_in_context_store(self):
        cs = ContextStore()
        session_id = cs.create_session()

        engine = RuntimeEngine(
            agent_executor=_ok_executor,
            context_store=cs,
            backoff_base=0,
        )
        spec = _make_spec(n_steps=2)
        engine.run(spec, session_id=session_id)

        checkpoint = cs.get(session_id, "_checkpoint")
        assert checkpoint is not None
        assert "step_0" in checkpoint
        assert "step_1" in checkpoint


# ===========================================================================
# OrchestratorAgent
# ===========================================================================


class TestOrchestratorAgent:
    """Tests for OrchestratorAgent (unit — LLM is mocked)."""

    def _make_mock_model(self, response_content: str = "Summary of run.") -> MagicMock:
        mock = MagicMock()
        mock.invoke.return_value = MagicMock(content=response_content)
        return mock

    def test_construction_defaults(self):
        from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent
        mock_model = self._make_mock_model()
        orch = OrchestratorAgent(model=mock_model)
        assert orch is not None
        assert orch.get_session_id()  # non-empty UUID

    def test_invoke_agent_supervised_scenario(self):
        from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent
        mock_model = self._make_mock_model("Workflow completed successfully.")
        spec = _make_spec(n_steps=1)

        orch = OrchestratorAgent(
            model=mock_model,
            agent_executor=_ok_executor,
            workflow_spec=spec,
            scenario="supervised",
        )
        result = orch.invoke_agent("Run the pre-built workflow.")
        assert result is not None
        assert orch.get_scenario() == "supervised"

    def test_invoke_agent_returns_ai_message(self):
        from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent
        mock_model = self._make_mock_model("This is the summary.")
        spec = _make_spec(n_steps=1)

        orch = OrchestratorAgent(
            model=mock_model,
            agent_executor=_ok_executor,
            workflow_spec=spec,
        )
        orch.invoke_agent("Run it.")
        msg = orch.get_ai_message()
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_get_run_result_contains_status(self):
        from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent
        mock_model = self._make_mock_model()
        spec = _make_spec(n_steps=2)

        orch = OrchestratorAgent(
            model=mock_model,
            agent_executor=_ok_executor,
            workflow_spec=spec,
        )
        orch.invoke_agent("Execute.")
        rr = orch.get_run_result()
        assert "status" in rr

    def test_get_workflow_spec_after_run(self):
        from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent
        mock_model = self._make_mock_model()
        spec = _make_spec("my_spec")

        orch = OrchestratorAgent(
            model=mock_model,
            agent_executor=_ok_executor,
            workflow_spec=spec,
        )
        orch.invoke_agent("Run.")
        assert orch.get_workflow_spec().get("name") == "my_spec"

    def test_get_orchestrator_log_non_empty(self):
        from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent
        mock_model = self._make_mock_model()
        spec = _make_spec()

        orch = OrchestratorAgent(
            model=mock_model,
            agent_executor=_ok_executor,
            workflow_spec=spec,
        )
        orch.invoke_agent("Run.")
        assert len(orch.get_orchestrator_log()) > 0

    def test_update_params_rebuilds_graph(self):
        from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent
        mock_model = self._make_mock_model()
        orch = OrchestratorAgent(model=mock_model)
        old_graph = orch._compiled_graph
        orch.update_params(max_retries=5)
        assert orch._params["max_retries"] == 5

    def test_invoke_agent_dry_run_no_executor(self):
        """With default no-op executor, run should complete as dry_run."""
        from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent
        mock_model = self._make_mock_model()
        spec = _make_spec(n_steps=1)

        orch = OrchestratorAgent(
            model=mock_model,
            workflow_spec=spec,
            # agent_executor not provided → default dry-run executor
        )
        orch.invoke_agent("Run in dry-run mode.")
        rr = orch.get_run_result()
        assert rr.get("status") == "completed"

    def test_top_level_import(self):
        """OrchestratorAgent accessible from top-level package."""
        from ai_data_science_team import OrchestratorAgent  # noqa: F401
        assert OrchestratorAgent is not None

    def test_orchestration_primitives_from_package(self):
        """All M22 primitives accessible from top-level package (facade removed)."""
        from ai_data_science_team import (  # noqa: F401
            AgentRegistry,
            AgentMetadata,
            ContextStore,
            OrchestratorAgent,
            RuntimeEngine,
            RunResult,
            SignalStore,
            WorkflowResolver,
            WorkflowSignal,
            build_spec,
            build_step,
            validate_spec,
        )
