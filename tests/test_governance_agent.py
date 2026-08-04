"""governance_agent modül yüzeyi + fabrika gerçek testleri (LLM-free).

Bu dosya yalnızca modülün export ettiği sabit isimleri (AGENT_NAME, NODE_TYPE,
GOVERNANCE_TOOLS), tool wrapper sınıflarının LangChain ``StructuredTool`` sözleşmesine
uyumluluğunu, ve ``make_governance_agent`` fabrikasının beklenen LangGraph node'larını
ürettiğini doğrular. **LLM çağrısı içermez** — bu yüzden hızlıdır ve LLM yokken
koşabilir.

Tool davranış testleri (9 tool) ``tests/llm/test_governance_agent_tool_calling.py``
altında **gerçek model-driven** olarak yazılmıştır. PM kararı: mock/stub yok.
"""

from __future__ import annotations

import sys

from ai_data_science_team.agents.governance_agent import (
    AGENT_NAME,
    GOVERNANCE_TOOLS,
    NODE_TYPE,
    make_governance_agent,
)

# ---------------------------------------------------------------------------
# 1. Modül yüzeyi (sabit isimler)
# ---------------------------------------------------------------------------


def test_constants():
    """AGENT_NAME lowercase spec_id + '_agent'; NODE_TYPE 'governance.evaluate'."""
    assert AGENT_NAME == "governance_agent"
    assert NODE_TYPE == "governance.evaluate"


def test_tool_registry_non_empty():
    assert len(GOVERNANCE_TOOLS) >= 1
    wrapper_names = {t.name for t in GOVERNANCE_TOOLS}
    assert len(wrapper_names) >= 1


def test_all_wrapper_names_follow_convention():
    """Tüm wrapper isimleri ``_wrapped`` ile bitmeli (template convention)."""
    wrapper_names = {t.name for t in GOVERNANCE_TOOLS}
    for wname in wrapper_names:
        assert wname.endswith("_wrapped"), f"{wname} must end with '_wrapped'"


# ---------------------------------------------------------------------------
# 2. Tool wrapper StructuredTool sözleşmesi
# ---------------------------------------------------------------------------

EXPECTED_WRAPPERS = [
    "assign_risk_wrapped",
    "required_approvers_wrapped",
    "start_approval_chain_wrapped",
    "approve_step_wrapped",
    "chain_progress_wrapped",
    "build_checklist_wrapped",
    "evaluate_checklist_wrapped",
    "render_audit_report_wrapped",
    "promotion_gate_wrapped",
]


def test_all_individual_tools_exported():
    """9 wrapper'ın hepsi modülden erişilebilir ve StructuredTool sözleşmesine sahip."""
    mod = sys.modules["ai_data_science_team.agents.governance_agent"]
    for wrapper_name in EXPECTED_WRAPPERS:
        wrapper = getattr(mod, wrapper_name)
        assert hasattr(wrapper, "name"), f"{wrapper_name} missing .name"
        assert hasattr(wrapper, "invoke"), f"{wrapper_name} missing .invoke"
        assert hasattr(wrapper, "func"), f"{wrapper_name} missing .func"


# ---------------------------------------------------------------------------
# 3. make_governance_agent fabrika wiring (LLM-free, no monkey-patch)
# ---------------------------------------------------------------------------


class _CallableModel:
    """``make_governance_agent`` yalnızca ``model`` argümanının callability'sini
    kontrol eder; bu stub, gerçek bir LLM çağrısı yapmaz. Aşağıdaki
    ``make_governance_agent`` testleri yalnızca graf düğümlerinin varlığını kontrol eder,
    invocation yapmaz; ``_CallableModel`` invoke edilse bile hiçbir yere
    çağrı yapılmaz."""

    def invoke(self, *args, **kwargs):
        raise NotImplementedError  # testler invoke etmemeli


def test_make_governance_agent_builds_graph():
    """make_governance_agent bir LangGraph StateGraph döndürmeli ve en azından
    reakt-agent + post_process node'larını içermeli."""
    graph = make_governance_agent(model=_CallableModel())
    # LangGraph Pregel nesnesi: .nodes dict'i
    node_ids = set(graph.nodes.keys()) if hasattr(graph, "nodes") else set()
    # en azından reakt-agent (veya benzeri) node + post_process
    assert len(node_ids) >= 1, f"make_governance_agent boş graph döndürdü: {node_ids}"
    # post_process düğümü her zaman olmalı (template convention)
    assert any("post" in n.lower() or "process" in n.lower() for n in node_ids), (
        f"graph içinde post_process node'u bulunamadı: {node_ids}"
    )
