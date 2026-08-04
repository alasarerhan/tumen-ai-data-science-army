"""champion_challenger_agent modül yüzeyi + fabrika gerçek testleri (LLM-free).

Bu dosya yalnızca modülün export ettiği sabit isimleri (AGENT_NAME, NODE_TYPE,
CHAMPION_CHALLENGER_TOOLS), tool wrapper sınıflarının LangChain ``StructuredTool`` sözleşmesine
uyumluluğunu, ve ``make_champion_challenger_agent`` fabrikasının beklenen LangGraph node'larını
ürettiğini doğrular. **LLM çağrısı içermez** — bu yüzden hızlıdır ve LLM yokken
koşabilir.

Tüm tool'lar stateful (Sequence[Any], bool); tool davranış testleri
**Faz C API entegrasyon testinde** kapsanacak. Bu yüzden tool_calling.py dosyası
oluşturulmadı.
"""

from __future__ import annotations

import sys

from ai_data_science_team.agents.champion_challenger_agent import (
    AGENT_NAME,
    CHAMPION_CHALLENGER_TOOLS,
    NODE_TYPE,
    make_champion_challenger_agent,
)

# ---------------------------------------------------------------------------
# 1. Modül yüzeyi (sabit isimler)
# ---------------------------------------------------------------------------


def test_constants():
    """AGENT_NAME lowercase spec_id + '_agent'; NODE_TYPE 'model.champion_challenger'."""
    assert AGENT_NAME == "champion_challenger_agent"
    assert NODE_TYPE == "model.champion_challenger"


def test_tool_registry_non_empty():
    assert len(CHAMPION_CHALLENGER_TOOLS) >= 1
    wrapper_names = {t.name for t in CHAMPION_CHALLENGER_TOOLS}
    assert len(wrapper_names) >= 1


def test_all_wrapper_names_follow_convention():
    """Tüm wrapper isimleri ``_wrapped`` ile bitmeli (template convention)."""
    wrapper_names = {t.name for t in CHAMPION_CHALLENGER_TOOLS}
    for wname in wrapper_names:
        assert wname.endswith("_wrapped"), f"{wname} must end with '_wrapped'"


# ---------------------------------------------------------------------------
# 2. Tool wrapper StructuredTool sözleşmesi
# ---------------------------------------------------------------------------

EXPECTED_WRAPPERS = [
    "mcnemar_test_wrapped",
    "wilcoxon_signed_rank_wrapped",
    "auc_with_delong_ci_wrapped",
    "delong_pvalue_wrapped",
    "compare_models_wrapped",
]


def test_all_individual_tools_exported():
    """5 wrapper'ın hepsi modülden erişilebilir ve StructuredTool sözleşmesine sahip."""
    mod = sys.modules["ai_data_science_team.agents.champion_challenger_agent"]
    for wrapper_name in EXPECTED_WRAPPERS:
        wrapper = getattr(mod, wrapper_name)
        assert hasattr(wrapper, "name"), f"{wrapper_name} missing .name"
        assert hasattr(wrapper, "invoke"), f"{wrapper_name} missing .invoke"
        assert hasattr(wrapper, "func"), f"{wrapper_name} missing .func"


# ---------------------------------------------------------------------------
# 3. make_champion_challenger_agent fabrika wiring (LLM-free, no monkey-patch)
# ---------------------------------------------------------------------------


class _CallableModel:
    """``make_champion_challenger_agent`` yalnızca ``model`` argümanının callability'sini
    kontrol eder; bu stub, gerçek bir LLM çağrısı yapmaz. Aşağıdaki
    ``make_champion_challenger_agent`` testleri yalnızca graf düğümlerinin varlığını kontrol eder,
    invocation yapmaz; ``_CallableModel`` invoke edilse bile hiçbir yere
    çağrı yapılmaz."""

    def invoke(self, *args, **kwargs):
        raise NotImplementedError  # testler invoke etmemeli


def test_make_champion_challenger_agent_builds_graph():
    """make_champion_challenger_agent bir LangGraph StateGraph döndürmeli ve en azından
    reakt-agent + post_process node'larını içermeli."""
    graph = make_champion_challenger_agent(model=_CallableModel())
    # LangGraph Pregel nesnesi: .nodes dict'i
    node_ids = set(graph.nodes.keys()) if hasattr(graph, "nodes") else set()
    # en azından reakt-agent (veya benzeri) node + post_process
    assert len(node_ids) >= 1, f"make_champion_challenger_agent boş graph döndürdü: {node_ids}"
    # post_process düğümü her zaman olmalı (template convention)
    assert any("post" in n.lower() or "process" in n.lower() for n in node_ids), (
        f"graph içinde post_process node'u bulunamadı: {node_ids}"
    )
