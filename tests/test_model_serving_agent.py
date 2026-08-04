"""model_serving_agent modül yüzeyi + fabrika gerçek testleri (LLM-free).

Bu dosya yalnızca modülün export ettiği sabit isimleri (AGENT_NAME, NODE_TYPE,
SERVING_TOOLS), tool wrapper sınıflarının LangChain ``StructuredTool`` sözleşmesine
uyumluluğunu, ve ``make_model_serving_agent`` fabrikasının beklenen LangGraph node'larını
ürettiğini doğrular. **LLM çağrısı içermez** — bu yüzden hızlıdır ve LLM yokken
koşabilir.

NOT: ModelServingAgent tool'ları ``_wrapped`` soneki kullanmaz (descriptive isimler:
load_model, run_inference, health_check, get_serving_params).

Tüm tool'lar stateful (InjectedState, file IO, mlflow, pickle); tool davranış testleri
**Faz C API entegrasyon testinde** kapsanacak. Bu yüzden tool_calling.py dosyası
oluşturulmadı.
"""

from __future__ import annotations

import sys

from ai_data_science_team.agents.model_serving_agent import (
    AGENT_NAME,
    NODE_TYPE,
    SERVING_TOOLS,
    make_model_serving_agent,
)

# ---------------------------------------------------------------------------
# 1. Modül yüzeyi (sabit isimler)
# ---------------------------------------------------------------------------


def test_constants():
    """AGENT_NAME 'model_serving_agent'; NODE_TYPE 'deploy.serve'."""
    assert AGENT_NAME == "model_serving_agent"
    assert NODE_TYPE == "deploy.serve"


def test_tool_registry_non_empty():
    assert len(SERVING_TOOLS) >= 1
    wrapper_names = {t.name for t in SERVING_TOOLS}
    assert len(wrapper_names) >= 1


def test_all_wrapper_names_follow_convention():
    """ModelServingAgent tool'ları descriptive isimler kullanır (``_wrapped`` soneki yok).
    Bu yüzden registry'deki tool isimleri kontrol edilir; ``_wrapped`` kuralı burada
    geçerli değildir."""
    wrapper_names = {t.name for t in SERVING_TOOLS}
    expected = {"load_model", "run_inference", "health_check", "get_serving_params"}
    assert expected.issubset(wrapper_names), (
        f"eksik tool: beklenen={expected}, bulunan={wrapper_names}"
    )


# ---------------------------------------------------------------------------
# 2. Tool wrapper StructuredTool sözleşmesi
# ---------------------------------------------------------------------------

EXPECTED_WRAPPERS = [
    "load_model",
    "run_inference",
    "health_check",
    "get_serving_params",
]


def test_all_individual_tools_exported():
    """4 wrapper'ın hepsi modülden erişilebilir ve StructuredTool sözleşmesine sahip."""
    mod = sys.modules["ai_data_science_team.agents.model_serving_agent"]
    for wrapper_name in EXPECTED_WRAPPERS:
        wrapper = getattr(mod, wrapper_name)
        assert hasattr(wrapper, "name"), f"{wrapper_name} missing .name"
        assert hasattr(wrapper, "invoke"), f"{wrapper_name} missing .invoke"
        assert hasattr(wrapper, "func"), f"{wrapper_name} missing .func"


# ---------------------------------------------------------------------------
# 3. make_model_serving_agent fabrika wiring (LLM-free, no monkey-patch)
# ---------------------------------------------------------------------------


class _CallableModel:
    """``make_model_serving_agent`` yalnızca ``model`` argümanının callability'sini
    kontrol eder; bu stub, gerçek bir LLM çağrısı yapmaz. Aşağıdaki
    ``make_model_serving_agent`` testleri yalnızca graf düğümlerinin varlığını kontrol eder,
    invocation yapmaz; ``_CallableModel`` invoke edilse bile hiçbir yere
    çağrı yapılmaz."""

    def invoke(self, *args, **kwargs):
        raise NotImplementedError  # testler invoke etmemeli


def test_make_model_serving_agent_builds_graph():
    """make_model_serving_agent bir LangGraph StateGraph döndürmeli ve en azından
    reakt-agent + post_process node'larını içermeli."""
    graph = make_model_serving_agent(model=_CallableModel())
    # LangGraph Pregel nesnesi: .nodes dict'i
    node_ids = set(graph.nodes.keys()) if hasattr(graph, "nodes") else set()
    # en azından reakt-agent (veya benzeri) node + post_process
    assert len(node_ids) >= 1, f"make_model_serving_agent boş graph döndürdü: {node_ids}"
    # post_process düğümü her zaman olmalı (template convention)
    assert any("post" in n.lower() or "process" in n.lower() for n in node_ids), (
        f"graph içinde post_process node'u bulunamadı: {node_ids}"
    )
