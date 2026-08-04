"""Tests for M11 — DataConnector interface and implementations.

Tests are intentionally self-contained (no live DB, no network).
SQLConnector tests use sqlite+pysqlite (stdlib), so no extra driver is needed.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_csv_dir(tmp_path: Path) -> Path:
    """Create a temp directory with two small CSV files."""
    (tmp_path / "sales.csv").write_text("date,revenue\n2024-01-01,100\n2024-01-02,200\n")
    (tmp_path / "costs.csv").write_text("date,cost\n2024-01-01,50\n2024-01-02,80\n")
    (tmp_path / "notes.txt").write_text("not a data file")  # should be ignored
    return tmp_path


# ---------------------------------------------------------------------------
# DataConnector ABC
# ---------------------------------------------------------------------------


def test_dataconnector_cannot_be_instantiated_directly():
    from ai_data_science_team.connectors.base import DataConnector

    with pytest.raises(TypeError):
        DataConnector()  # abstract


def test_dataconnector_minimal_subclass():
    """A minimal concrete subclass must implement all abstract methods."""
    from ai_data_science_team.connectors.base import DataConnector

    class MinimalConnector(DataConnector):
        @property
        def name(self) -> str:
            return "minimal"

        def connect(self, **kw: Any) -> None:
            pass

        def list_sources(self) -> List[str]:
            return ["source_a"]

        def read(self, source: str, *, max_rows=None, columns=None, **kw) -> pd.DataFrame:
            return pd.DataFrame({"x": [1, 2, 3]})

        def health_check(self) -> Dict[str, Any]:
            return {"status": "ok", "connector": self.name}

    conn = MinimalConnector()
    assert conn.name == "minimal"
    assert conn.list_sources() == ["source_a"]
    assert conn.health_check()["status"] == "ok"
    assert repr(conn) == "<MinimalConnector name='minimal'>"


def test_dataconnector_context_manager():
    from ai_data_science_team.connectors.base import DataConnector

    connected = []

    class CtxConnector(DataConnector):
        @property
        def name(self) -> str:
            return "ctx"

        def connect(self, **kw: Any) -> None:
            connected.append(True)

        def close(self) -> None:
            connected.append(False)

        def list_sources(self) -> List[str]:
            return []

        def read(self, source: str, *, max_rows=None, columns=None, **kw) -> pd.DataFrame:
            return pd.DataFrame()

        def health_check(self) -> Dict[str, Any]:
            return {"status": "ok", "connector": self.name}

    with CtxConnector():
        pass

    assert connected == [True, False]


# ---------------------------------------------------------------------------
# LocalFileConnector
# ---------------------------------------------------------------------------


def test_local_file_connector_list_sources(tmp_csv_dir: Path):
    from ai_data_science_team.connectors import LocalFileConnector

    conn = LocalFileConnector(str(tmp_csv_dir))
    conn.connect()
    sources = conn.list_sources()
    assert "costs.csv" in sources
    assert "sales.csv" in sources
    # non-CSV file should be excluded
    assert not any("notes.txt" in s for s in sources)


def test_local_file_connector_read_csv(tmp_csv_dir: Path):
    from ai_data_science_team.connectors import LocalFileConnector

    conn = LocalFileConnector(str(tmp_csv_dir))
    conn.connect()
    df = conn.read("sales.csv")
    assert list(df.columns) == ["date", "revenue"]
    assert len(df) == 2


def test_local_file_connector_max_rows(tmp_csv_dir: Path):
    from ai_data_science_team.connectors import LocalFileConnector

    conn = LocalFileConnector(str(tmp_csv_dir))
    conn.connect()
    df = conn.read("sales.csv", max_rows=1)
    assert len(df) == 1


def test_local_file_connector_columns(tmp_csv_dir: Path):
    from ai_data_science_team.connectors import LocalFileConnector

    conn = LocalFileConnector(str(tmp_csv_dir))
    conn.connect()
    df = conn.read("sales.csv", columns=["revenue"])
    assert list(df.columns) == ["revenue"]


def test_local_file_connector_file_type_filter(tmp_csv_dir: Path):
    # Add a parquet file to the directory
    import pandas as pd

    pd.DataFrame({"a": [1]}).to_parquet(tmp_csv_dir / "data.parquet")

    from ai_data_science_team.connectors import LocalFileConnector

    conn = LocalFileConnector(str(tmp_csv_dir), file_type="csv")
    conn.connect()
    sources = conn.list_sources()
    assert all(s.endswith(".csv") for s in sources)
    assert "data.parquet" not in sources


def test_local_file_connector_missing_dir_raises():
    from ai_data_science_team.connectors import LocalFileConnector

    conn = LocalFileConnector("/nonexistent/path/xyz")
    with pytest.raises(ConnectionError):
        conn.connect()


def test_local_file_connector_missing_source_raises(tmp_csv_dir: Path):
    from ai_data_science_team.connectors import LocalFileConnector

    conn = LocalFileConnector(str(tmp_csv_dir))
    conn.connect()
    with pytest.raises(FileNotFoundError):
        conn.read("does_not_exist.csv")


def test_local_file_connector_health_ok(tmp_csv_dir: Path):
    from ai_data_science_team.connectors import LocalFileConnector

    conn = LocalFileConnector(str(tmp_csv_dir))
    conn.connect()
    h = conn.health_check()
    assert h["status"] == "ok"
    assert h["source_count"] == 2  # sales.csv + costs.csv


# ---------------------------------------------------------------------------
# SQLConnector (SQLite in-memory)
# ---------------------------------------------------------------------------


@pytest.fixture()
def sqlite_conn():
    from ai_data_science_team.connectors import SQLConnector

    conn = SQLConnector("sqlite:///:memory:")
    conn.connect()

    # Seed a test table
    import sqlalchemy as sa

    with conn._engine.connect() as c:
        c.execute(sa.text("CREATE TABLE orders (id INTEGER, amount REAL)"))
        c.execute(sa.text("INSERT INTO orders VALUES (1, 99.9), (2, 49.5), (3, 199.0)"))
        c.commit()

    yield conn
    conn.close()


def test_sql_connector_list_sources(sqlite_conn):
    sources = sqlite_conn.list_sources()
    # SQLite default schema is 'main'
    assert "main.orders" in sources


def test_sql_connector_read(sqlite_conn):
    df = sqlite_conn.read("main.orders")
    assert list(df.columns) == ["id", "amount"]
    assert len(df) == 3


def test_sql_connector_read_max_rows(sqlite_conn):
    df = sqlite_conn.read("main.orders", max_rows=2)
    assert len(df) == 2


def test_sql_connector_health_ok(sqlite_conn):
    h = sqlite_conn.health_check()
    assert h["status"] == "ok"
    assert h["dialect"] == "sqlite"


def test_sql_connector_invalid_url_raises():
    from ai_data_science_team.connectors import SQLConnector

    conn = SQLConnector("postgresql://bad_host_xyz:9999/nonexistent_db")
    with pytest.raises(Exception):
        conn.connect()


# ---------------------------------------------------------------------------
# load_connector_plugins
# ---------------------------------------------------------------------------


def test_load_connector_plugins_returns_dict():
    from ai_data_science_team.connectors import load_connector_plugins

    result = load_connector_plugins()
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------


def _make_server_with_csv(tmp_csv_dir: Path):
    from ai_data_science_team.connectors import LocalFileConnector
    from plugins.connectors.mcp_server.server import MCPServer

    conn = LocalFileConnector(str(tmp_csv_dir))
    conn.connect()
    return MCPServer(connector=conn)


def test_mcp_server_initialize(tmp_csv_dir: Path):
    srv = _make_server_with_csv(tmp_csv_dir)
    resp = srv.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert resp["result"]["protocolVersion"] == "2024-11-05"
    assert "tools" in resp["result"]["capabilities"]


def test_mcp_server_ping(tmp_csv_dir: Path):
    srv = _make_server_with_csv(tmp_csv_dir)
    resp = srv.handle_request({"jsonrpc": "2.0", "id": 2, "method": "ping"})
    assert resp["result"] == {}


def test_mcp_server_tools_list(tmp_csv_dir: Path):
    srv = _make_server_with_csv(tmp_csv_dir)
    resp = srv.handle_request({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
    tool_names = [t["name"] for t in resp["result"]["tools"]]
    assert "list_sources" in tool_names
    assert "read_source" in tool_names
    assert "connector_health" in tool_names


def test_mcp_server_tool_call_list_sources(tmp_csv_dir: Path):
    srv = _make_server_with_csv(tmp_csv_dir)
    resp = srv.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "list_sources", "arguments": {}},
        }
    )
    text = resp["result"]["content"][0]["text"]
    assert "sales.csv" in text


def test_mcp_server_tool_call_read_source(tmp_csv_dir: Path):
    srv = _make_server_with_csv(tmp_csv_dir)
    resp = srv.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "read_source", "arguments": {"source": "sales.csv"}},
        }
    )
    csv_text = resp["result"]["content"][0]["text"]
    assert "revenue" in csv_text


def test_mcp_server_resources_list(tmp_csv_dir: Path):
    srv = _make_server_with_csv(tmp_csv_dir)
    resp = srv.handle_request({"jsonrpc": "2.0", "id": 6, "method": "resources/list"})
    uris = [r["uri"] for r in resp["result"]["resources"]]
    assert any("sales.csv" in u for u in uris)


def test_mcp_server_resources_read(tmp_csv_dir: Path):
    srv = _make_server_with_csv(tmp_csv_dir)
    resp = srv.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "resources/read",
            "params": {"uri": "connector://local_file/sales.csv"},
        }
    )
    text = resp["result"]["contents"][0]["text"]
    assert "revenue" in text


def test_mcp_server_unknown_method_returns_error(tmp_csv_dir: Path):
    srv = _make_server_with_csv(tmp_csv_dir)
    resp = srv.handle_request({"jsonrpc": "2.0", "id": 99, "method": "no_such_method"})
    assert "error" in resp
    assert resp["error"]["code"] == -32601


def test_mcp_server_notification_returns_none(tmp_csv_dir: Path):
    """Notifications (no id) must not produce a response."""
    srv = _make_server_with_csv(tmp_csv_dir)
    resp = srv.handle_request({"jsonrpc": "2.0", "method": "initialized"})
    assert resp is None


def test_mcp_server_io_loop(tmp_csv_dir: Path):
    """Verify the full I/O loop writes valid JSON-RPC responses."""
    from ai_data_science_team.connectors import LocalFileConnector
    from plugins.connectors.mcp_server.server import MCPServer

    conn = LocalFileConnector(str(tmp_csv_dir))
    conn.connect()

    requests = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
    ]
    input_stream = io.StringIO("\n".join(requests) + "\n")
    output_stream = io.StringIO()

    srv = MCPServer(connector=conn, input_stream=input_stream, output_stream=output_stream)
    srv.run()

    output_stream.seek(0)
    lines = [line_ for line_ in output_stream.readlines() if line_.strip()]
    assert len(lines) == 2
    responses = [json.loads(line_) for line_ in lines]
    assert responses[0]["id"] == 1
    assert responses[1]["id"] == 2
    assert "tools" in responses[1]["result"]
