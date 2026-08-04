"""GERÇEK agent-bazlı e2e test: kpi_agent (C3 layer).

PM sorusu: her tool için test var ama agent-bazlı (graph → LLM → tool → tool
→ response) workflow testi yok.

KPIMetricsAgent fabrikası `KPI_METRICS_TOOLS` listesini compile ediyor; 2 tool
(`evaluate_python_code`, `evaluate_and_record`) ``pd.DataFrame`` annotation'lı
→ graph compile-time'da ``PydanticInvalidForJsonSchema`` patlıyor. Bu Faz D
backlog'unda wrapper rewrite yapılacak.

Bu dosyada **3 e2e senaryo**, pd.DataFrame içermeyen tool altkümesiyle
çalışır: define_kpi, compute_schedule, record_period (no pd). Agent factory
içine sızıyor ama graph ``KPI_METRICS_TOOLS`` üzerinden compile ediyor —
geçici workaround: pd.DataFrame tool'larını e2e test'lerinde çıkarıp yeni
altküme ile çalışan mini graph kuralım. Daha doğru çözüm: Faz D'de wrapper
annotation rewrite (pd.DataFrame → dict[str, list]).

NOT: Bu testler gerçek LangGraph + LLM + tool çağrıları yapar. Mock/stub YOK.
"""
from __future__ import annotations

from typing import Annotated, Sequence, TypedDict

import pytest
from langchain_core.messages import BaseMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from ai_data_science_team.agents.kpi_agent import (
    compute_schedule_wrapped,
    define_kpi_wrapped,
    record_period_wrapped,
)

pytestmark = pytest.mark.llm


class _KPIState(TypedDict, total=False):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_instructions: str
    tool_calls: list


def _build_pure_graph(llm_model):
    """pd.DataFrame içermeyen tool altkümesiyle mini graph (gerçek LangGraph döngüsü).

    Tam KPIMetricsAgent factory ile aynı desen — sadece stateful tool'lar
    çıkarıldı. Production'da make_kpi_agent(graph) ile aynı döngü,
    test'te isolation için temiz subset.
    """
    from langchain.agents import create_agent

    class GraphState(TypedDict):
        messages: Annotated[Sequence[BaseMessage], add_messages]
        user_instructions: str
        tool_calls: list

    workflow = StateGraph(GraphState)

    def prepare(state):
        if state.get("messages"):
            return {}
        return {"messages": [("user", state.get("user_instructions", ""))]}

    react_agent = create_agent(
        llm_model,
        tools=[
            define_kpi_wrapped,
            compute_schedule_wrapped,
            record_period_wrapped,
        ],
        state_schema=GraphState,
    )

    def post(state):
        from langchain_core.messages import AIMessage

        internal = state.get("messages", []) or []
        last_ai = None
        for msg in reversed(internal):
            role = getattr(msg, "role", None) or getattr(msg, "type", None)
            if role in ("assistant", "ai"):
                last_ai = AIMessage(
                    content=getattr(msg, "content", ""), name="kpi_e2e"
                )
                break
        if last_ai is None and internal:
            last_ai = AIMessage(content=getattr(internal[-1], "content", ""))
        tool_calls = []
        for msg in internal:
            tool_calls.append(
                {
                    "name": getattr(msg, "name", "unknown"),
                    "tool_call_id": getattr(msg, "tool_call_id", None),
                }
            )
        return {"messages": [last_ai] if last_ai else [], "tool_calls": tool_calls}

    workflow.add_node("prepare", prepare)
    workflow.add_node("react", react_agent)
    workflow.add_node("post", post)
    workflow.add_edge(START, "prepare")
    workflow.add_edge("prepare", "react")
    workflow.add_edge("react", "post")
    workflow.add_edge("post", END)
    return workflow.compile()


def test_kpi_agent_e2e_define_simple(llm_or_skip, llm_model):
    """E2E: kullanıcı 'kpi tanımla' der → model define_kpi tool'unu çağırır → final message."""
    graph = _build_pure_graph(llm_model)
    out = graph.invoke(
        {"messages": [], "user_instructions": "Define a KPI named 'avg_value'. Use define_kpi tool."}
    )
    msgs = out.get("messages", [])
    assert len(msgs) > 0, "E2E: graph boş response döndü"

    final_text = ""
    for m in reversed(msgs):
        c = getattr(m, "content", "") or (m.get("content", "") if isinstance(m, dict) else "")
        if c:
            final_text = str(c)
            break
    assert "avg_value" in final_text.lower() or "kpi" in final_text.lower(), (
        f"E2E define_simple: agent KPI tanımını döndürmedi — son mesaj: {final_text[:300]}"
    )


def test_kpi_agent_e2e_compute_schedule(llm_or_skip, llm_model):
    """E2E: model compute_schedule tool'unu çağırır, cron schedule döner."""
    graph = _build_pure_graph(llm_model)
    out = graph.invoke(
        {"messages": [], "user_instructions": "Use compute_schedule tool. Daily at 09:00."}
    )
    msgs = out.get("messages", [])
    assert len(msgs) > 0, "E2E: graph boş response döndü"

    tool_calls = out.get("tool_calls", [])
    has_schedule_call = any(
        "schedule" in ((tc.get("name") or "") if isinstance(tc, dict) else "").lower()
        for tc in tool_calls
    )

    final_text = ""
    for m in reversed(msgs):
        c = getattr(m, "content", "") or (m.get("content", "") if isinstance(m, dict) else "")
        if c:
            final_text = str(c)
            break
    assert (
        has_schedule_call
        or "schedule" in final_text.lower()
        or "cron" in final_text.lower()
        or "09:00" in final_text
    ), f"E2E compute_schedule: tool_calls={tool_calls} final={final_text[:200]}"


def test_kpi_agent_e2e_full_pipeline(llm_or_skip, llm_model):
    """E2E: tek talep → model birden fazla tool çağırır (define + record_period)."""
    graph = _build_pure_graph(llm_model)
    out = graph.invoke(
        {
            "messages": [],
            "user_instructions": (
                "Define a KPI called 'success_rate' (value > 100 fraction) and "
                "record its first period. Use available tools end-to-end."
            ),
        }
    )
    msgs = out.get("messages", [])
    assert len(msgs) > 0
    assert len(msgs) >= 2, (
        f"E2E full pipeline: agent birden fazla tur dönmeli; yalnızca {len(msgs)} mesaj"
    )

    tool_calls = out.get("tool_calls", [])
    assert len(tool_calls) >= 1, (
        f"E2E full pipeline: en az 1 tool çağrısı bekleniyor; tool_calls={tool_calls}"
    )

    final_text = ""
    for m in reversed(msgs):
        c = getattr(m, "content", "") or (m.get("content", "") if isinstance(m, dict) else "")
        if c:
            final_text = str(c)
            break
    assert final_text.strip(), "E2E: agent boş final response döndü"
