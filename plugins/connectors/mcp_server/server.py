"""Reference MCP (Model Context Protocol) stdio server (M11).

Implements the core MCP JSON-RPC 2.0 message loop over stdin/stdout so that
any ``DataConnector`` can be consumed by MCP-aware clients (Claude Desktop,
Continue.dev, any LLM that speaks MCP, etc.).

Supported MCP methods
---------------------
initialize            Handshake; returns server capabilities and protocol version.
tools/list            Enumerate available tools (one per DataConnector operation).
tools/call            Execute a tool and return the result.
resources/list        Enumerate available data sources.
resources/read        Read a data source and return its content.
ping                  Health check.

Protocol notes
--------------
- All messages are newline-delimited JSON (NDJSON) on stdin / stdout.
- Errors follow JSON-RPC 2.0 ``{"jsonrpc":"2.0","id":...,"error":{...}}``.
- The server runs until EOF on stdin or a SIGINT/SIGTERM signal.

References
----------
https://modelcontextprotocol.io/docs/concepts/architecture
https://spec.modelcontextprotocol.io/specification/basic/messages/
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, Optional

from ai_data_science_team.connectors.base import DataConnector

# ---------------------------------------------------------------------------
# MCP protocol constants
# ---------------------------------------------------------------------------

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "ai-data-science-team-connector"
SERVER_VERSION = "0.1.0"

_JSONRPC = "2.0"

# ---------------------------------------------------------------------------
# Tool definitions exposed by this server
# ---------------------------------------------------------------------------

_TOOL_LIST_SOURCES = {
    "name": "list_sources",
    "description": "List all available data source identifiers (file paths, table names, etc.).",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

_TOOL_READ_SOURCE = {
    "name": "read_source",
    "description": (
        "Read a data source and return its content as CSV text. "
        "Use list_sources first to discover valid source identifiers."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": "Source identifier returned by list_sources.",
            },
            "max_rows": {
                "type": "integer",
                "description": "Maximum number of rows to return (default 500).",
                "default": 500,
            },
        },
        "required": ["source"],
    },
}

_TOOL_HEALTH = {
    "name": "connector_health",
    "description": "Return the health status of the underlying DataConnector.",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

_ALL_TOOLS = [_TOOL_LIST_SOURCES, _TOOL_READ_SOURCE, _TOOL_HEALTH]


# ---------------------------------------------------------------------------
# MCPServer
# ---------------------------------------------------------------------------


class MCPServer:
    """Minimal stdio MCP server backed by a ``DataConnector``.

    Parameters
    ----------
    connector:
        An already-connected (or auto-connecting) ``DataConnector`` instance.
    input_stream:
        Defaults to ``sys.stdin``.  Override for testing.
    output_stream:
        Defaults to ``sys.stdout``.  Override for testing.
    """

    def __init__(
        self,
        connector: DataConnector,
        input_stream=None,
        output_stream=None,
    ) -> None:
        self._connector = connector
        self._in = input_stream or sys.stdin
        self._out = output_stream or sys.stdout
        self._initialized = False

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the JSON-RPC request/response loop (blocking)."""
        try:
            self._connector.connect()
        except Exception as exc:
            self._write_error(
                None, code=-32603, message=f"Connector connect() failed: {exc}"
            )

        for raw_line in self._in:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                request = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                self._write_error(None, code=-32700, message=f"Parse error: {exc}")
                continue

            try:
                response = self._dispatch(request)
            except Exception as exc:  # noqa: BLE001
                req_id = request.get("id")
                self._write_error(req_id, code=-32603, message=str(exc))
                continue

            if response is not None:
                self._write(response)

    def handle_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single parsed JSON-RPC request and return the response dict.

        Useful for testing without running the full I/O loop.
        """
        return self._dispatch(request)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        method: str = req.get("method", "")
        req_id = req.get("id")
        params: Dict[str, Any] = req.get("params") or {}

        # Notifications (no id) — process but don't respond
        is_notification = req_id is None

        match method:
            case "initialize":
                result = self._handle_initialize(params)
            case "initialized":
                return None  # notification, no response
            case "ping":
                result = {}
            case "tools/list":
                result = {"tools": _ALL_TOOLS}
            case "tools/call":
                result = self._handle_tool_call(params)
            case "resources/list":
                result = self._handle_resources_list()
            case "resources/read":
                result = self._handle_resources_read(params)
            case _:
                if is_notification:
                    return None
                return self._error_response(
                    req_id, code=-32601, message=f"Method not found: {method}"
                )

        if is_notification:
            return None
        return {"jsonrpc": _JSONRPC, "id": req_id, "result": result}

    # ------------------------------------------------------------------
    # Method handlers
    # ------------------------------------------------------------------

    def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self._initialized = True
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"listChanged": False, "subscribe": False},
            },
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }

    def _handle_tool_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        tool_name: str = params.get("name", "")
        args: Dict[str, Any] = params.get("arguments") or {}

        if tool_name == "list_sources":
            sources = self._connector.list_sources()
            text = "\n".join(sources) if sources else "(no sources found)"
            return {"content": [{"type": "text", "text": text}]}

        if tool_name == "read_source":
            source = args.get("source")
            if not source:
                raise ValueError("'source' argument is required for read_source")
            max_rows = int(args.get("max_rows", 500))
            df = self._connector.read(source, max_rows=max_rows)
            csv_text = df.to_csv(index=False)
            return {"content": [{"type": "text", "text": csv_text}]}

        if tool_name == "connector_health":
            health = self._connector.health_check()
            return {"content": [{"type": "text", "text": json.dumps(health, indent=2)}]}

        raise ValueError(f"Unknown tool: {tool_name}")

    def _handle_resources_list(self) -> Dict[str, Any]:
        sources = self._connector.list_sources()
        resources = [
            {
                "uri": f"connector://{self._connector.name}/{src}",
                "name": src,
                "mimeType": "text/csv",
            }
            for src in sources
        ]
        return {"resources": resources}

    def _handle_resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        uri: str = params.get("uri", "")
        # uri format: connector://<name>/<source>
        prefix = f"connector://{self._connector.name}/"
        source = uri.removeprefix(prefix) if uri.startswith(prefix) else uri
        if not source:
            raise ValueError(f"Cannot resolve source from URI: {uri}")
        df = self._connector.read(source, max_rows=500)
        csv_text = df.to_csv(index=False)
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "text/csv",
                    "text": csv_text,
                }
            ]
        }

    # ------------------------------------------------------------------
    # I/O helpers
    # ------------------------------------------------------------------

    def _write(self, payload: Dict[str, Any]) -> None:
        line = json.dumps(payload, ensure_ascii=False)
        print(line, file=self._out, flush=True)

    def _write_error(self, req_id: Any, *, code: int, message: str) -> None:
        self._write(self._error_response(req_id, code=code, message=message))

    @staticmethod
    def _error_response(req_id: Any, *, code: int, message: str) -> Dict[str, Any]:
        return {
            "jsonrpc": _JSONRPC,
            "id": req_id,
            "error": {"code": code, "message": message},
        }


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m plugins.connectors.mcp_server.server",
        description="Start the MCP stdio server backed by a DataConnector.",
    )
    source = p.add_mutually_exclusive_group()
    source.add_argument(
        "--base-dir",
        metavar="DIR",
        help="Use LocalFileConnector with this base directory.",
    )
    source.add_argument(
        "--db",
        metavar="URL",
        help="Use SQLConnector with this SQLAlchemy connection URL.",
    )
    p.add_argument(
        "--file-type",
        metavar="EXT",
        help="(LocalFileConnector only) filter by file extension, e.g. 'csv'.",
    )
    p.add_argument(
        "--recursive",
        action="store_true",
        help="(LocalFileConnector only) scan sub-directories recursively.",
    )
    return p


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.db:
        from ai_data_science_team.connectors import SQLConnector
        connector: DataConnector = SQLConnector(args.db)
    else:
        from ai_data_science_team.connectors import LocalFileConnector
        connector = LocalFileConnector(
            base_dir=args.base_dir,
            recursive=args.recursive,
            file_type=args.file_type,
        )

    server = MCPServer(connector=connector)
    server.run()


if __name__ == "__main__":
    main()
