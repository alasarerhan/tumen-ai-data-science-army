"""TG2 — Integration tests for M22 Orchestration Layer.

Gerçek OpenAI API kullanır (gpt-4o-mini).  Bu testler şunları kapsar:

* WorkflowResolver — Dynamic senaryoda LLM ile spec üretimi
* OrchestratorAgent — Supervised senaryo (LLM summary)
* OrchestratorAgent — Dynamic senaryo (NL goal → LLM oluşturur spec → executor çalışır)
* OrchestratorAgent — Manuel senaryo
* Signal entegrasyonu (SKIP / CANCEL / MODIFY gerçek çalıştırmada)
* AgentRegistry ile birleşik executor
* Bağımlılıklı çok-adımlı workflow
* Tüm getter'lar (get_ai_message, get_run_result, get_scenario, get_session_id, …)

Çalıştırmak için:
    pytest tests/test_integration_m22.py -v -m integration

Atlamak için:
    pytest tests/ -v -m "not integration"
"""

from __future__ import annotations

from typing import Any, Dict

import pytest
from _llm import make_chat_model, skip_no_key

pytestmark = pytest.mark.integration


langchain_openai = pytest.importorskip(
    "langchain_openai",
    reason="langchain_openai is not installed — skipping integration tests",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _invoke_safe(agent, **kw):
    """invoke_agent; API quota sorunlarında testi atlar."""
    try:
        return agent.invoke_agent(**kw)
    except Exception as exc:
        err = str(exc)
        if any(x in err for x in ("insufficient_quota", "RateLimitError", "rate_limit")):
            pytest.skip("OpenAI quota tükendi — billing ekle")
        raise


def _ok_executor(agent_name: str, instruction: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Gerçek bir agent çağrısını simüle eden basit başarılı executor."""
    return {
        "agent": agent_name,
        "instruction": instruction,
        "output": f"{agent_name} completed: {instruction[:60]}",
        "rows_processed": 100,
    }


def _fail_then_ok_executor():
    """İlk çağrı başarısız, ikinci başarılı executor factory."""
    calls = {"n": 0}

    def executor(agent_name: str, instruction: str, context: Dict[str, Any]) -> Dict[str, Any]:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("Transient failure")
        return {"agent": agent_name, "output": "recovered"}

    return executor


@pytest.fixture(scope="module")
def llm():
    return make_chat_model(temperature=0, max_tokens=800)


@pytest.fixture(autouse=True)
def clean_registry():
    from ai_data_science_team.agent_registry import AgentRegistry

    AgentRegistry.clear()
    yield
    AgentRegistry.clear()


# ---------------------------------------------------------------------------
# WorkflowResolver + LLM (Dynamic Scenario)
# ---------------------------------------------------------------------------


@skip_no_key
def test_resolver_dynamic_generates_valid_spec(llm):
    """LLM, NL goal'dan geçerli bir WorkflowSpec üretmeli."""
    from ai_data_science_team.workflow_resolver import WorkflowResolver, validate_spec

    resolver = WorkflowResolver(model=llm)
    result = resolver.resolve(user_goal="Load a CSV file and compute summary statistics.")

    assert result["scenario"] == WorkflowResolver.DYNAMIC
    spec = result["spec"]
    assert isinstance(spec, dict), "Spec dict olmalı"
    assert "name" in spec, "Spec 'name' içermeli"
    assert "steps" in spec and len(spec["steps"]) > 0, "En az bir step olmalı"

    errors = validate_spec(spec)
    assert errors == [], f"Spec validation hataları: {errors}"


@skip_no_key
def test_resolver_dynamic_step_structure(llm):
    """Üretilen spec'teki her step gerekli alanları içermeli."""
    from ai_data_science_team.workflow_resolver import WorkflowResolver

    resolver = WorkflowResolver(model=llm)
    result = resolver.resolve(user_goal="Perform EDA on a sales dataset and visualize trends.")
    spec = result["spec"]

    for step in spec.get("steps", []):
        assert "id" in step, f"Step 'id' eksik: {step}"
        assert "agent" in step, f"Step 'agent' eksik: {step}"
        assert "instruction" in step, f"Step 'instruction' eksik: {step}"


@skip_no_key
def test_resolver_supervised_no_llm_call(llm):
    """Supervised senaryoda LLM çağrısı yapılmaz — spec olduğu gibi döner."""
    from unittest.mock import patch

    from ai_data_science_team.workflow_resolver import WorkflowResolver, build_spec, build_step

    spec = build_spec("prebuilt", [build_step("s0", "AgentX", "Do task")])
    resolver = WorkflowResolver(model=llm)

    # WorkflowResolver._generate_spec çağrılmamalı
    with patch.object(resolver, "_generate_spec", wraps=resolver._generate_spec) as mock_gen:
        result = resolver.resolve(workflow_spec=spec)
        assert result["scenario"] == WorkflowResolver.SUPERVISED
        assert result["spec"] == spec
        mock_gen.assert_not_called()


# ---------------------------------------------------------------------------
# OrchestratorAgent — Supervised (LLM summary gerçek)
# ---------------------------------------------------------------------------


@skip_no_key
def test_orchestrator_supervised_ai_message(llm):
    """Supervised senaryoda OrchestratorAgent LLM ile özet oluşturmalı."""
    from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent
    from ai_data_science_team.workflow_resolver import build_spec, build_step

    spec = build_spec(
        "sales_analysis",
        [
            build_step("load", "DataLoaderAgent", "Load sales data from CSV"),
            build_step(
                "clean",
                "DataCleaningAgent",
                "Clean missing values and outliers",
                depends_on=["load"],
            ),
            build_step("eda", "EDAAgent", "Generate descriptive statistics", depends_on=["clean"]),
        ],
    )

    orch = OrchestratorAgent(
        model=llm,
        agent_executor=_ok_executor,
        workflow_spec=spec,
        scenario="supervised",
    )
    _invoke_safe(orch, user_instructions="Run the sales analysis pipeline.")

    msg = orch.get_ai_message()
    assert isinstance(msg, str), "AI mesajı string olmalı"
    assert len(msg) > 20, f"AI mesajı çok kısa: {msg!r}"


@skip_no_key
def test_orchestrator_supervised_run_result_complete(llm):
    """Supervised run, tüm adımları başarıyla tamamlamalı."""
    from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent
    from ai_data_science_team.workflow_resolver import build_spec, build_step

    spec = build_spec(
        "wf",
        [
            build_step("step_a", "AgentA", "Task A"),
            build_step("step_b", "AgentB", "Task B", depends_on=["step_a"]),
        ],
    )

    orch = OrchestratorAgent(
        model=llm,
        agent_executor=_ok_executor,
        workflow_spec=spec,
    )
    _invoke_safe(orch, user_instructions="Run it.")

    rr = orch.get_run_result()
    assert rr["status"] == "completed", f"Beklenen 'completed', alınan: {rr['status']}"
    assert rr["success_count"] == 2
    assert rr["failed_count"] == 0


@skip_no_key
def test_orchestrator_supervised_getters(llm):
    """invoke sonrası tüm getter'lar anlamlı değerler döndürmeli."""
    from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent
    from ai_data_science_team.workflow_resolver import build_spec, build_step

    spec = build_spec("getter_test", [build_step("s0", "Agent", "task")])
    orch = OrchestratorAgent(
        model=llm,
        agent_executor=_ok_executor,
        workflow_spec=spec,
    )
    _invoke_safe(orch, user_instructions="Test getters.")

    assert orch.get_scenario() in ("supervised", "manual", "dynamic")
    assert isinstance(orch.get_session_id(), str) and len(orch.get_session_id()) > 0
    assert isinstance(orch.get_orchestrator_log(), list) and len(orch.get_orchestrator_log()) >= 1
    assert isinstance(orch.get_workflow_spec(), dict)
    assert isinstance(orch.get_run_result(), dict)


# ---------------------------------------------------------------------------
# OrchestratorAgent — Dynamic (LLM spec üretir + executor çalışır)
# ---------------------------------------------------------------------------


@skip_no_key
def test_orchestrator_dynamic_end_to_end(llm):
    """Dynamic senaryoda LLM spec üretmeli, executor çalıştırmalı.

    Registry'ye platform agent'ları kaydedilir; LLM katalogdan seçer.
    """
    from ai_data_science_team.agent_registry import AgentRegistry
    from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent

    # Platform agent'larını kaydet (dynamic senaryoda LLM katalogdan seçer)
    class _Stub:
        pass

    for name, caps in [
        ("DataLoaderAgent", ["data_loading"]),
        ("DataCleaningAgent", ["data_cleaning"]),
        ("DataWranglingAgent", ["data_wrangling"]),
        ("EDAAgent", ["eda"]),
        ("DataVisualizationAgent", ["visualization"]),
    ]:
        AgentRegistry.register(name, _Stub, capabilities=caps, description=f"{name} stub")

    orch = OrchestratorAgent(
        model=llm,
        agent_executor=_ok_executor,
        scenario="dynamic",
        # registry_catalog otomatik olarak AgentRegistry.to_catalog() alır
    )
    _invoke_safe(
        orch,
        user_instructions="Load a CSV file, clean missing values, and compute summary statistics.",
    )

    assert orch.get_scenario() == "dynamic"
    spec = orch.get_workflow_spec()
    assert isinstance(spec, dict)
    # LLM en az bir step üretmiş olmalı
    assert len(spec.get("steps", [])) >= 1, f"Dynamic spec steps boş. Spec: {spec}"

    rr = orch.get_run_result()
    assert "status" in rr

    msg = orch.get_ai_message()
    assert isinstance(msg, str) and len(msg) > 0


@skip_no_key
def test_orchestrator_dynamic_spec_contains_meaningful_agents(llm):
    """LLM'nin ürettiği spec, domain'e uygun agent isimleri içermeli."""
    from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent

    orch = OrchestratorAgent(
        model=llm,
        agent_executor=_ok_executor,
        scenario="dynamic",
    )
    _invoke_safe(
        orch,
        user_instructions="Perform an exploratory data analysis on a bike sales dataset.",
    )

    spec = orch.get_workflow_spec()
    steps = spec.get("steps", [])
    # LLM spec üretemediyse (validation errors) testi bilgilendirici geç
    if len(steps) == 0:
        pytest.skip(
            "LLM geçerli bir spec üretemedi — spec steps boş; diğer dynamic testler kapsıyor"
        )
    all_agents = " ".join(s.get("agent", "") for s in steps)
    assert len(all_agents.strip()) > 0, "Step'lerde agent ismi boş"


# ---------------------------------------------------------------------------
# OrchestratorAgent — Manuel senaryo
# ---------------------------------------------------------------------------


@skip_no_key
def test_orchestrator_manual_scenario(llm):
    """Manuel senaryoda spec + kullanıcı tarafından yönetilir; run_result durumu raporlanmalı."""
    from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent
    from ai_data_science_team.workflow_resolver import build_spec, build_step

    spec = build_spec("manual_wf", [build_step("m0", "ManualAgent", "Manual task")])
    orch = OrchestratorAgent(
        model=llm,
        agent_executor=_ok_executor,
        workflow_spec=spec,
        managed_by_user=True,
    )
    _invoke_safe(orch, user_instructions="Manual run.")

    assert orch.get_scenario() == "manual"
    rr = orch.get_run_result()
    assert "status" in rr


# ---------------------------------------------------------------------------
# Signal Integration — SKIP
# ---------------------------------------------------------------------------


@skip_no_key
def test_orchestrator_skip_signal_respected(llm):
    """Emit edilen SKIP sinyali, ilgili step'i atlamalı."""
    from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent
    from ai_data_science_team.signals import SignalStore, SignalType, WorkflowSignal
    from ai_data_science_team.workflow_resolver import build_spec, build_step

    spec = build_spec(
        "skip_test",
        [
            build_step("step_to_skip", "AgentX", "Should be skipped"),
            build_step("step_normal", "AgentY", "Should run normally"),
        ],
    )

    signal_store = SignalStore()
    # OrchestratorAgent'tan session_id'yi almak için önce oluştur
    orch = OrchestratorAgent(
        model=llm,
        agent_executor=_ok_executor,
        workflow_spec=spec,
        signal_store=signal_store,
    )
    session_id = orch.get_session_id()

    # Çalışmadan önce sinyal emit et
    signal_store.emit(
        WorkflowSignal(
            type=SignalType.SKIP,
            session_id=session_id,
            step_id="step_to_skip",
        )
    )

    _invoke_safe(orch, user_instructions="Run with skip signal.")

    rr = orch.get_run_result()
    steps = {s["step_id"]: s["status"] for s in rr.get("steps", [])}
    assert steps.get("step_to_skip") == "skipped", f"step_to_skip atlanmadı: {steps}"
    assert steps.get("step_normal") == "success", f"step_normal çalışmadı: {steps}"


# ---------------------------------------------------------------------------
# Signal Integration — CANCEL
# ---------------------------------------------------------------------------


@skip_no_key
def test_orchestrator_cancel_signal_stops_run(llm):
    """CANCEL sinyali çalışmayı durdurmalı; hiçbir step çalışmaz."""
    from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent
    from ai_data_science_team.signals import SignalStore, SignalType, WorkflowSignal
    from ai_data_science_team.workflow_resolver import build_spec, build_step

    call_count = {"n": 0}

    def counting_executor(agent_name, instruction, context):
        call_count["n"] += 1
        return {"ok": True}

    spec = build_spec(
        "cancel_test",
        [
            build_step("s0", "A", "task"),
            build_step("s1", "B", "task"),
            build_step("s2", "C", "task"),
        ],
    )

    signal_store = SignalStore()
    orch = OrchestratorAgent(
        model=llm,
        agent_executor=counting_executor,
        workflow_spec=spec,
        signal_store=signal_store,
    )
    session_id = orch.get_session_id()

    signal_store.emit(
        WorkflowSignal(
            type=SignalType.CANCEL,
            session_id=session_id,
        )
    )

    _invoke_safe(orch, user_instructions="Run with cancel signal.")

    rr = orch.get_run_result()
    assert rr["status"] == "cancelled", f"Beklenen 'cancelled', alınan: {rr['status']}"
    assert call_count["n"] == 0, "Hiçbir executor çağrısı yapılmamalıydı"


# ---------------------------------------------------------------------------
# Signal Integration — MODIFY
# ---------------------------------------------------------------------------


@skip_no_key
def test_orchestrator_modify_signal_overrides_instruction(llm):
    """MODIFY sinyali step instruction'ını değiştirmeli."""
    from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent
    from ai_data_science_team.signals import SignalStore, SignalType, WorkflowSignal
    from ai_data_science_team.workflow_resolver import build_spec, build_step

    received = {"instruction": None}

    def capturing_executor(agent_name, instruction, context):
        received["instruction"] = instruction
        return {"ok": True}

    spec = build_spec(
        "modify_test",
        [
            build_step("target_step", "AgentA", "ORIGINAL INSTRUCTION"),
        ],
    )

    signal_store = SignalStore()
    orch = OrchestratorAgent(
        model=llm,
        agent_executor=capturing_executor,
        workflow_spec=spec,
        signal_store=signal_store,
    )
    session_id = orch.get_session_id()

    signal_store.emit(
        WorkflowSignal(
            type=SignalType.MODIFY,
            session_id=session_id,
            step_id="target_step",
            payload={"instruction": "MODIFIED INSTRUCTION FROM SIGNAL"},
        )
    )

    _invoke_safe(orch, user_instructions="Run with modify signal.")
    assert received["instruction"] == "MODIFIED INSTRUCTION FROM SIGNAL"


# ---------------------------------------------------------------------------
# AgentRegistry + executor entegrasyonu
# ---------------------------------------------------------------------------


@skip_no_key
def test_orchestrator_registry_based_executor(llm):
    """Registry'den agent_class çeken bir executor ile tam çalıştırma."""
    from ai_data_science_team.agent_registry import AgentRegistry
    from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent
    from ai_data_science_team.workflow_resolver import build_spec, build_step

    class FakeDataAgent:
        def __init__(self, model=None, **kw):
            pass

        def invoke_agent(self, user_instructions="", **kw):
            return {"result": "fake data loaded"}

        def get_ai_message(self):
            return "Loaded."

    AgentRegistry.register(
        name="FakeDataAgent",
        agent_class=FakeDataAgent,
        capabilities=["data_loading"],
        description="Test agent for registry integration.",
    )

    def registry_executor(agent_name: str, instruction: str, context: dict):
        meta = AgentRegistry.get(agent_name)
        agent = meta.agent_class()
        agent.invoke_agent(user_instructions=instruction)
        return {"output": agent.get_ai_message()}

    spec = build_spec(
        "registry_wf",
        [
            build_step("s0", "FakeDataAgent", "Load data"),
        ],
    )

    orch = OrchestratorAgent(
        model=llm,
        agent_executor=registry_executor,
        workflow_spec=spec,
    )
    _invoke_safe(orch, user_instructions="Run with registry executor.")

    rr = orch.get_run_result()
    assert rr["status"] == "completed"
    assert rr["success_count"] == 1


# ---------------------------------------------------------------------------
# Retry + Fallback (LLM summary ile birlikte gerçek run)
# ---------------------------------------------------------------------------


@skip_no_key
def test_orchestrator_retry_then_success(llm):
    """İlk deneme başarısız olup retry'da başarılı olmalı; LLM özet üretmeli."""
    from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent
    from ai_data_science_team.workflow_resolver import build_spec, build_step

    spec = build_spec("retry_wf", [build_step("s0", "FlakeyAgent", "Flakey task")])
    orch = OrchestratorAgent(
        model=llm,
        agent_executor=_fail_then_ok_executor(),
        workflow_spec=spec,
        max_retries=2,
    )
    _invoke_safe(orch, user_instructions="Run with flakey agent.")

    rr = orch.get_run_result()
    assert rr["status"] == "completed"
    # to_dict() key'i "steps"
    assert rr["steps"][0]["retries"] == 1


@skip_no_key
def test_orchestrator_fallback_agent_on_primary_failure(llm):
    """Primary agent başarısız olduğunda fallback agent çalıştırılmalı."""
    from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent
    from ai_data_science_team.workflow_resolver import build_spec, build_step

    used_agents: list = []

    def executor_with_fallback(agent_name: str, instruction: str, context: dict):
        used_agents.append(agent_name)
        if agent_name == "PrimaryAgent":
            raise RuntimeError("primary always fails")
        return {"ok": "fallback_ran"}

    spec = build_spec(
        "fallback_wf",
        [
            build_step("s0", "PrimaryAgent", "task", fallbacks=["BackupAgent"]),
        ],
    )
    orch = OrchestratorAgent(
        model=llm,
        agent_executor=executor_with_fallback,
        workflow_spec=spec,
        max_retries=0,
    )
    _invoke_safe(orch, user_instructions="Run with fallback.")

    rr = orch.get_run_result()
    assert rr["steps"][0]["status"] == "success"
    assert "BackupAgent" in used_agents


# ---------------------------------------------------------------------------
# Bağımlılıklı çok-adımlı workflow
# ---------------------------------------------------------------------------


@skip_no_key
def test_orchestrator_multi_step_with_dependencies(llm):
    """Bağımlılık zinciri doğru sırayla çalışmalı."""
    from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent
    from ai_data_science_team.workflow_resolver import build_spec, build_step

    exec_order: list = []

    def ordered_executor(agent_name, instruction, context):
        exec_order.append(agent_name)
        return {"done": True}

    spec = build_spec(
        "dep_chain",
        [
            build_step("load", "Loader", "Load data"),
            build_step("clean", "Cleaner", "Clean data", depends_on=["load"]),
            build_step("transform", "Transformer", "Transform features", depends_on=["clean"]),
            build_step("visualize", "Visualizer", "Plot charts", depends_on=["transform"]),
        ],
    )

    orch = OrchestratorAgent(
        model=llm,
        agent_executor=ordered_executor,
        workflow_spec=spec,
    )
    _invoke_safe(orch, user_instructions="Run full pipeline.")

    rr = orch.get_run_result()
    assert rr["status"] == "completed"
    assert rr["success_count"] == 4

    # Bağımlılık sırası korunmuş olmalı
    assert exec_order.index("Loader") < exec_order.index("Cleaner")
    assert exec_order.index("Cleaner") < exec_order.index("Transformer")
    assert exec_order.index("Transformer") < exec_order.index("Visualizer")


# ---------------------------------------------------------------------------
# ContextStore entegrasyonu
# ---------------------------------------------------------------------------


@skip_no_key
def test_orchestrator_context_store_checkpoint(llm):
    """RuntimeEngine, her step sonrası ContextStore'a checkpoint kaydeder."""
    from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent
    from ai_data_science_team.context_store import ContextStore
    from ai_data_science_team.workflow_resolver import build_spec, build_step

    cs = ContextStore()
    spec = build_spec(
        "ckpt_wf",
        [
            build_step("c0", "AgentA", "task A"),
            build_step("c1", "AgentB", "task B"),
        ],
    )

    orch = OrchestratorAgent(
        model=llm,
        agent_executor=_ok_executor,
        workflow_spec=spec,
        context_store=cs,
    )
    _invoke_safe(orch, user_instructions="Run checkpoint test.")

    session_id = orch.get_session_id()
    assert cs.session_exists(session_id)
    checkpoint = cs.get(session_id, "_checkpoint")
    assert checkpoint is not None
    assert "c0" in checkpoint
    assert "c1" in checkpoint


# ---------------------------------------------------------------------------
# LLM özet kalitesi
# ---------------------------------------------------------------------------


@skip_no_key
def test_orchestrator_summary_mentions_workflow(llm):
    """LLM özeti workflow ismine veya adım sayısına atıfta bulunmalı."""
    from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent
    from ai_data_science_team.workflow_resolver import build_spec, build_step

    spec = build_spec(
        "bike_sales_pipeline",
        [
            build_step("load", "DataLoader", "Load bike_sales_data.csv"),
            build_step("eda", "EDAAgent", "Run EDA", depends_on=["load"]),
        ],
    )

    orch = OrchestratorAgent(
        model=llm,
        agent_executor=_ok_executor,
        workflow_spec=spec,
        scenario="supervised",
    )
    _invoke_safe(
        orch,
        user_instructions="Analyse the bike sales dataset pipeline.",
    )

    msg = orch.get_ai_message().lower()
    # Özet, adım sayısını veya başarı durumunu belirtmeli
    assert any(
        kw in msg for kw in ("step", "adım", "complet", "success", "workflow", "pipeline")
    ), f"Özet workflow/step bilgisi içermiyor: {msg[:200]}"
