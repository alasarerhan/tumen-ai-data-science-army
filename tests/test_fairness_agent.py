"""fairness_agent modül yüzeyi + fabrika gerçek testleri (LLM-free).

Bu dosya yalnızca modülün export ettiği sabit isimleri (AGENT_NAME, NODE_TYPE,
FAIRNESS_AUDIT_TOOLS), tool wrapper sınıflarının LangChain ``StructuredTool`` sözleşmesine
uyumluluğunu, ve ``make_fairness_agent`` fabrikasının beklenen LangGraph node'larını
ürettiğini doğrular. **LLM çağrısı içermez** — bu yüzden hızlıdır ve LLM yokken
koşabilir.

Tüm tool'lar stateful (pd.DataFrame, Sequence); tool davranış testleri
**Faz C API entegrasyon testinde** kapsanacak. Bu yüzden tool_calling.py dosyası
oluşturulmadı.
"""

from __future__ import annotations

import sys

from ai_data_science_team.agents.fairness_agent import (
    AGENT_NAME,
    FAIRNESS_AUDIT_TOOLS,
    NODE_TYPE,
    make_fairness_agent,
)

# ---------------------------------------------------------------------------
# 1. Modül yüzeyi (sabit isimler)
# ---------------------------------------------------------------------------


def test_constants():
    """AGENT_NAME lowercase spec_id + '_agent'; NODE_TYPE 'model.fairness_audit'."""
    assert AGENT_NAME == "fairness_agent"
    assert NODE_TYPE == "model.fairness_audit"


def test_tool_registry_non_empty():
    assert len(FAIRNESS_AUDIT_TOOLS) >= 1
    wrapper_names = {t.name for t in FAIRNESS_AUDIT_TOOLS}
    assert len(wrapper_names) >= 1


def test_all_wrapper_names_follow_convention():
    """Tüm wrapper isimleri ``_wrapped`` ile bitmeli (template convention)."""
    wrapper_names = {t.name for t in FAIRNESS_AUDIT_TOOLS}
    for wname in wrapper_names:
        assert wname.endswith("_wrapped"), f"{wname} must end with '_wrapped'"


# ---------------------------------------------------------------------------
# 2. Tool wrapper StructuredTool sözleşmesi
# ---------------------------------------------------------------------------

EXPECTED_WRAPPERS = [
    "per_group_metrics_wrapped",
    "demographic_parity_difference_wrapped",
    "demographic_parity_ratio_wrapped",
    "equalized_odds_difference_wrapped",
    "violates_four_fifths_wrapped",
    "simulate_threshold_mitigation_wrapped",
    "audit_fairness_wrapped",
]


def test_all_individual_tools_exported():
    """7 wrapper'ın hepsi modülden erişilebilir ve StructuredTool sözleşmesine sahip."""
    mod = sys.modules["ai_data_science_team.agents.fairness_agent"]
    for wrapper_name in EXPECTED_WRAPPERS:
        wrapper = getattr(mod, wrapper_name)
        assert hasattr(wrapper, "name"), f"{wrapper_name} missing .name"
        assert hasattr(wrapper, "invoke"), f"{wrapper_name} missing .invoke"
        assert hasattr(wrapper, "func"), f"{wrapper_name} missing .func"


# ---------------------------------------------------------------------------
# 3. make_fairness_agent fabrika wiring (LLM-free, no monkey-patch)
# ---------------------------------------------------------------------------


class _CallableModel:
    """``make_fairness_agent`` yalnızca ``model`` argümanının callability'sini
    kontrol eder; bu stub, gerçek bir LLM çağrısı yapmaz. Aşağıdaki
    ``make_fairness_agent`` testleri yalnızca graf düğümlerinin varlığını kontrol eder,
    invocation yapmaz; ``_CallableModel`` invoke edilse bile hiçbir yere
    çağrı yapılmaz."""

    def invoke(self, *args, **kwargs):
        raise NotImplementedError  # testler invoke etmemeli


def test_make_fairness_agent_builds_graph():
    """make_fairness_agent bir LangGraph StateGraph döndürmeli ve en azından
    reakt-agent + post_process node'larını içermeli."""
    graph = make_fairness_agent(model=_CallableModel())
    # LangGraph Pregel nesnesi: .nodes dict'i
    node_ids = set(graph.nodes.keys()) if hasattr(graph, "nodes") else set()
    # en azından reakt-agent (veya benzeri) node + post_process
    assert len(node_ids) >= 1, f"make_fairness_agent boş graph döndürdü: {node_ids}"
    # post_process düğümü her zaman olmalı (template convention)
    assert any("post" in n.lower() or "process" in n.lower() for n in node_ids), (
        f"graph içinde post_process node'u bulunamadı: {node_ids}"
    )
