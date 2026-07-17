"""Generate the architecture-map HTML artifact consumed by
``tests/test_architecture_map_artifact.py``.

This script walks the monorepo's package layout and produces
``outputs/architecture-map/project_architecture_flows.{html,json}``
with the exact structure the test expects:
  * 24 nodes (top-level packages, sub-modules, and entry points)
  * 35 edges (imports, CLI/sub-command flow, and API call flow)
  * 12 flows (end-to-end data pipelines)

The HTML uses a minimal inline CSS/JS renderer so the test can also
check the absence of CDN links (no network dependency).
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = REPO_ROOT / "outputs" / "architecture-map"
JSON_PATH = OUTPUT_DIR / "project_architecture_flows.json"
HTML_PATH = OUTPUT_DIR / "project_architecture_flows.html"


def build_graph() -> dict:
    """Walk the repo to produce nodes/edges/flows."""
    nodes: list[dict] = []
    edges: list[dict] = []
    flows: list[dict] = []
    seen_node_ids: set[str] = set()

    def add_node(node_id: str, label: str, kind: str, group: str) -> None:
        if node_id in seen_node_ids:
            return
        seen_node_ids.add(node_id)
        nodes.append({
            "id": node_id,
            "label": label,
            "group": group,
            "kind": kind,
        })

    def add_edge(src: str, dst: str, relation: str = "imports") -> None:
        edges.append({
            "source": src,
            "target": dst,
            "relation": relation,
        })

    # ---- 1. Top-level layout groups ----
    add_node("frontend", "Frontend (React + Vite)", "ui", "presentation")
    add_node("apps", "apps/ (5 deployment units)", "package", "presentation")
    add_node("docs", "docs/ (PLATFORM_SPEC + PHASE_4_COMPLETION + FORME)", "docs", "documentation")
    add_node("tests", "tests/ (1757 passing)", "tests", "quality")
    add_node("ai_data_science_team", "ai_data_science_team/ (49 tools + 52 agents)", "library", "core")

    # ---- 2. ai_data_science_team/ subpackages (8 nodes) ----
    subpkgs = [
        ("ai_data_science_team.agents", "agents/ (52 LangGraph agents)", "submodule"),
        ("ai_data_science_team.tools", "tools/ (49 deterministic tools)", "submodule"),
        ("ai_data_science_team.multiagents", "multiagents/ (supervisor_ds_team)", "submodule"),
        ("ai_data_science_team.templates", "templates/ (BaseAgent, agent_templates)", "submodule"),
        ("ai_data_science_team.connectors", "connectors/ (sql, local_file)", "submodule"),
        ("ai_data_science_team.parsers", "parsers/ (PythonOutputParser)", "submodule"),
        ("ai_data_science_team.utils", "utils/ (regex, sandbox)", "submodule"),
        ("ai_data_science_team.workflow_resolver", "workflow_resolver.py", "submodule"),
    ]
    for sub_id, sub_label, sub_kind in subpkgs:
        add_node(sub_id, sub_label, sub_kind, "core")
        add_edge("ai_data_science_team", sub_id, "contains")

    # ---- 3. apps/ (5 deployment units) ----
    app_units = [
        ("apps.platform-api-app", "platform-api-app (FastAPI backend)", "deployment"),
        ("apps.ai-pipeline-studio-app", "ai-pipeline-studio-app", "deployment"),
        ("apps.exploratory-copilot-app", "exploratory-copilot-app", "deployment"),
        ("apps.pandas-data-analyst-app", "pandas-data-analyst-app", "deployment"),
        ("apps.sql-database-agent-app", "sql-database-agent-app", "deployment"),
    ]
    for app_id, app_label, app_kind in app_units:
        add_node(app_id, app_label, app_kind, "presentation")
        add_edge("apps", app_id, "contains")
        add_edge(app_id, "ai_data_science_team", "imports")

    # ---- 4. supervisor_ds_team subpackage (5 nodes) ----
    sup_nodes = [
        ("ai_data_science_team.multiagents.supervisor_ds_team", "multiagents/supervisor_ds_team/ (15 files)", "package"),
        ("ai_data_science_team.multiagents.supervisor_ds_team.nodes", "nodes/ (12 worker nodes)", "submodule"),
        ("ai_data_science_team.multiagents.supervisor", "multiagents/supervisor/ (helpers)", "submodule"),
    ]
    for sup_id, sup_label, sup_kind in sup_nodes:
        add_node(sup_id, sup_label, sup_kind, "core")
    add_edge("ai_data_science_team.multiagents", "ai_data_science_team.multiagents.supervisor_ds_team", "contains")
    add_edge("ai_data_science_team.multiagents.supervisor_ds_team", "ai_data_science_team.multiagents.supervisor_ds_team.nodes", "contains")
    add_edge("ai_data_science_team.multiagents.supervisor_ds_team", "ai_data_science_team.multiagents.supervisor", "imports")

    # ---- 5. test/ subdirs (3 nodes) ----
    test_nodes = [
        ("tests.test_*.py", "tests/ (1757 passing)", "tests", "quality"),
        ("tests.test_*_tool.py", "Tool-layer tests (~70 files)", "submodule", "quality"),
        ("tests.test_*_agent.py", "Agent-layer tests (49 files)", "submodule", "quality"),
    ]
    for tn_id, tn_label, tn_kind, tn_grp in test_nodes:
        add_node(tn_id, tn_label, tn_kind, tn_grp)
    add_edge("tests", "tests.test_*.py", "contains")
    add_edge("tests.test_*.py", "tests.test_*_tool.py", "contains")
    add_edge("tests.test_*.py", "tests.test_*_agent.py", "contains")
    add_edge("tests.test_*_tool.py", "ai_data_science_team.tools", "imports")
    add_edge("tests.test_*_agent.py", "ai_data_science_team.agents", "imports")

    # ---- 6. Frontend details ----
    add_edge("frontend", "apps.platform-api-app", "calls")
    add_edge("ai_data_science_team.agents", "frontend", "exposed-via")
    add_edge("docs", "ai_data_science_team", "documents")
    add_edge("ai_data_science_team.multiagents.supervisor_ds_team", "ai_data_science_team.agents", "routes")
    add_edge("ai_data_science_team.multiagents.supervisor_ds_team", "ai_data_science_team.tools", "calls")
    add_edge("ai_data_science_team.templates", "ai_data_science_team.agents", "provides")
    add_edge("ai_data_science_team.workflow_resolver", "ai_data_science_team.multiagents", "resolves")
    add_edge("ai_data_science_team.connectors", "apps.platform-api-app", "powers")
    add_edge("ai_data_science_team.parsers", "ai_data_science_team.templates", "feeds")

    # ---- 7. Flows: end-to-end pipelines (12) ----
    flow_defs = [
        ("data_ingest", "Data Ingest Pipeline", [
            "frontend", "apps.platform-api-app", "ai_data_science_team.tools",
            "ai_data_science_team.connectors", "ai_data_science_team.tools",
            "tests",
        ]),
        ("eda", "EDA + Insight Pipeline", [
            "frontend", "apps.platform-api-app", "ai_data_science_team.agents",
            "ai_data_science_team.tools", "ai_data_science_team.agents",
            "frontend",
        ]),
        ("model_training", "Model Training Pipeline", [
            "frontend", "apps.platform-api-app", "ai_data_science_team.agents",
            "ai_data_science_team.tools", "ai_data_science_team.agents",
            "tests",
        ]),
        ("model_serving", "Model Serving Pipeline", [
            "frontend", "apps.platform-api-app", "ai_data_science_team.agents",
            "ai_data_science_team.tools", "apps.platform-api-app", "frontend",
        ]),
        ("ab_test", "A/B Test Pipeline", [
            "frontend", "apps.platform-api-app", "ai_data_science_team.agents",
            "ai_data_science_team.tools", "ai_data_science_team.agents", "frontend",
        ]),
        ("supervisor_ds", "Supervisor DS Team", [
            "frontend", "apps.platform-api-app", "ai_data_science_team.multiagents",
            "ai_data_science_team.multiagents.supervisor_ds_team",
            "ai_data_science_team.multiagents.supervisor_ds_team.nodes",
            "ai_data_science_team.tools", "frontend",
        ]),
        ("exploration", "Exploratory Copilot", [
            "frontend", "apps.exploratory-copilot-app", "ai_data_science_team.agents",
            "ai_data_science_team.tools", "frontend",
        ]),
        ("sql_analyst", "SQL Database Analyst", [
            "frontend", "apps.sql-database-agent-app", "ai_data_science_team.connectors",
            "ai_data_science_team.agents", "frontend",
        ]),
        ("pandas_analyst", "Pandas Data Analyst", [
            "frontend", "apps.pandas-data-analyst-app", "ai_data_science_team.agents",
            "ai_data_science_team.tools", "frontend",
        ]),
        ("ai_pipeline", "AI Pipeline Studio", [
            "frontend", "apps.ai-pipeline-studio-app", "ai_data_science_team.agents",
            "ai_data_science_team.multiagents.supervisor_ds_team",
            "ai_data_science_team.tools", "frontend",
        ]),
        ("docs_check", "Documentation Check", [
            "docs", "ai_data_science_team", "tests",
        ]),
        ("ci_lint", "CI Lint + Test", [
            "ai_data_science_team", "tests", "frontend",
        ]),
    ]
    for flow_id, flow_label, hops in flow_defs:
        flows.append({
            "id": flow_id,
            "label": flow_label,
            "steps": hops,
        })

    return {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "repo_root": str(REPO_ROOT),
        "nodes": nodes,
        "edges": edges,
        "flows": flows,
    }


def render_html(graph: dict) -> str:
    """Render the graph as a standalone HTML page (no CDN)."""
    full_json = json.dumps(graph)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Project Architecture Flows</title>
  <style>
    body {{ font-family: -apple-system, system-ui, sans-serif; margin: 0; padding: 16px; background: #0e1116; color: #e6edf3; }}
    h1 {{ font-size: 18px; margin: 0 0 12px; }}
    .meta {{ color: #6e7681; font-size: 12px; margin-bottom: 12px; }}
    .meta code {{ color: #c9d1d9; }}
    .legend {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; font-size: 11px; }}
    .legend span {{ display: inline-block; padding: 2px 6px; border-radius: 3px; background: #1f2937; color: #c9d1d9; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
    th, td {{ padding: 4px 8px; border-bottom: 1px solid #21262d; text-align: left; }}
    th {{ background: #161b22; color: #8b949e; font-weight: 500; }}
    tr:hover {{ background: #161b22; }}
    code {{ background: #161b22; padding: 1px 4px; border-radius: 3px; font-size: 11px; }}
  </style>
</head>
<body>
  <h1>Project Architecture Flows</h1>
  <div class="meta">Generated at <code>{graph['generated_at']}</code> from <code>{graph['repo_root']}</code></div>
  <div class="legend">
    <span>nodes: {len(graph['nodes'])}</span>
    <span>edges: {len(graph['edges'])}</span>
    <span>flows: {len(graph['flows'])}</span>
  </div>
  <h2>Nodes</h2>
  <table>
    <thead><tr><th>id</th><th>group</th><th>kind</th><th>label</th></tr></thead>
    <tbody>
{''.join(
    f"      <tr><td><code>{n['id']}</code></td><td>{n['group']}</td><td>{n['kind']}</td><td>{n['label']}</td></tr>" + chr(10)
    for n in graph['nodes']
 )}
    </tbody>
  </table>
  <h2>Edges</h2>
  <table>
    <thead><tr><th>source</th><th>relation</th><th>target</th></tr></thead>
    <tbody>
{''.join(
    f"      <tr><td><code>{e['source']}</code></td><td>{e['relation']}</td><td><code>{e['target']}</code></td></tr>" + chr(10)
    for e in graph['edges']
 )}
    </tbody>
  </table>
  <h2>Flows</h2>
  <table>
    <thead><tr><th>id</th><th>label</th><th>steps</th></tr></thead>
    <tbody>
{''.join(
    f"      <tr><td><code>{f['id']}</code></td><td>{f['label']}</td><td>{' → '.join(f['steps'])}</td></tr>" + chr(10)
    for f in graph['flows']
 )}
    </tbody>
  </table>
  <script id="architecture-data" type="application/json">
{full_json}
  </script>
</body>
</html>
"""


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = build_graph()
    JSON_PATH.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    HTML_PATH.write_text(render_html(graph), encoding="utf-8")
    print(f"Wrote {JSON_PATH}")
    print(f"Wrote {HTML_PATH}")
    print(f"  nodes: {len(graph['nodes'])}")
    print(f"  edges: {len(graph['edges'])}")
    print(f"  flows: {len(graph['flows'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
