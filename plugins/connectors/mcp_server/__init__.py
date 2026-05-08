"""plugins.connectors.mcp_server — Reference MCP (Model Context Protocol) server (M11).

This package contains a minimal, stdio-based MCP server that wraps any
``DataConnector`` and exposes its sources as MCP *tools*.

MCP specification: https://spec.modelcontextprotocol.io/

Usage (CLI)
-----------
Launch against the built-in LocalFileConnector::

    python -m plugins.connectors.mcp_server.server --base-dir /path/to/data

Launch against a SQLite database::

    python -m plugins.connectors.mcp_server.server --db sqlite:///mydb.sqlite

Programmatic usage
------------------
    from plugins.connectors.mcp_server.server import MCPServer
    from ai_data_science_team.connectors import LocalFileConnector

    conn = LocalFileConnector("/data")
    conn.connect()
    srv = MCPServer(connector=conn)
    srv.run()   # starts the stdio event loop
"""
