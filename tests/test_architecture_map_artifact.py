"""Test that the generated architecture-map HTML artifact is correct.

The test generates the map from the library functions so it never
depends on pre-existing build artifacts on disk.
"""
from __future__ import annotations

import json

from tools.generate_architecture_map import build_graph, render_html


def test_architecture_map_html_is_standalone_and_embeds_full_json() -> None:
    graph = build_graph()
    html = render_html(graph)

    assert len(graph["nodes"]) == 24, f"Expected 24 nodes, got {len(graph['nodes'])}"
    assert len(graph["edges"]) == 35, f"Expected 35 edges, got {len(graph['edges'])}"
    assert len(graph["flows"]) == 12, f"Expected 12 flows, got {len(graph['flows'])}"

    # The embedded JSON in the HTML must round-trip correctly.
    expected = json.dumps(graph)
    start = html.index('<script id="architecture-data" type="application/json">')
    content_start = html.index("\n", start) + 1
    end = html.index("\n  </script>", content_start)
    embedded = json.loads(html[content_start:end])

    # The embedded data must be identical to the source graph dict.
    assert json.loads(expected) == embedded

    # The HTML must *not* depend on CDN-hosted resources.
    assert "https://cdn.tailwindcss.com" not in html
