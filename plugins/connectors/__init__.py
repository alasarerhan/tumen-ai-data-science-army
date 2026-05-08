"""plugins.connectors — reference DataConnector plugins (M11).

Included
--------
mcp_server/    Minimal stdio-based MCP server that exposes any DataConnector
               as a set of Model Context Protocol tools.

How to add your own plugin
--------------------------
1. Create a new sub-package here or in a separate installable distribution.
2. Subclass ``ai_data_science_team.connectors.DataConnector``.
3. Register via entry-point ``ai_data_science_team.connectors`` in pyproject.toml.
"""
