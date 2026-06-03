from __future__ import annotations

import json
from pathlib import Path


def test_architecture_map_html_is_standalone_and_embeds_full_json() -> None:
    html_path = Path("outputs/architecture-map/project_architecture_flows.html")
    json_path = Path("outputs/architecture-map/project_architecture_flows.json")

    html = html_path.read_text(encoding="utf-8")
    expected = json.loads(json_path.read_text(encoding="utf-8"))
    start = html.index('<script id="architecture-data" type="application/json">')
    content_start = html.index("\n", start) + 1
    end = html.index("\n  </script>", content_start)
    embedded = json.loads(html[content_start:end])

    assert "https://cdn.tailwindcss.com" not in html
    assert embedded == expected
    assert len(embedded["nodes"]) == 24
    assert len(embedded["edges"]) == 35
    assert len(embedded["flows"]) == 12
