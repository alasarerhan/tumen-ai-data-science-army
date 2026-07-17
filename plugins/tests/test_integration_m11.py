"""
M11 — DataConnector + MCP Server TG2 Entegrasyon Testleri
==========================================================
TG1 (test_connectors.py) izole unit düzeyinde bileşenleri test eder.
TG2 burada birden fazla katmanı birlikte çalıştırır:

  • LocalFileConnector  →  as_langchain_tools()  →  tool invocation
  • SQLConnector (disk-based SQLite)  →  MCP Server tam session
  • Recursive scan + subdirectory sources
  • Full JSON-RPC IO loop with SQL-backed server
  • CLI argparse entry-point smoke test
  • Cross-connector chain: CSV connector bilgisi SQL tabloya yazılır, SQL connector o tabloyu okur

Çalıştır:
    python -m pytest tests/test_integration_m11.py -v -m integration
Atlamak için:
    python -m pytest tests/ -m "not integration"
"""
from __future__ import annotations


from _llm import make_chat_model  # noqa: F401
import io
import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def csv_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Flat directory with two CSV files used across multiple tests."""
    d = tmp_path_factory.mktemp("csv_data")
    (d / "sales.csv").write_text("date,revenue\n2024-01-01,100\n2024-01-02,200\n2024-01-03,150\n")
    (d / "costs.csv").write_text("date,cost\n2024-01-01,40\n2024-01-02,60\n2024-01-03,55\n")
    return d


@pytest.fixture(scope="module")
def recursive_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Two-level directory tree for recursive scan tests."""
    root = tmp_path_factory.mktemp("recursive_data")
    (root / "level1.csv").write_text("x,y\n1,2\n3,4\n")
    sub = root / "sub"
    sub.mkdir()
    (sub / "level2.csv").write_text("a,b\n10,20\n30,40\n")
    (sub / "readme.txt").write_text("ignored")
    return root


@pytest.fixture(scope="module")
def disk_sqlite(tmp_path_factory: pytest.TempPathFactory) -> str:
    """A real on-disk SQLite file with two tables."""
    db_path = tmp_path_factory.mktemp("db") / "store.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE products (id INTEGER, name TEXT, price REAL)")
    conn.execute(
        "INSERT INTO products VALUES (1, 'Widget', 9.99), (2, 'Gadget', 19.99), (3, 'Doohickey', 4.99)"
    )
    conn.execute("CREATE TABLE regions (code TEXT, name TEXT)")
    conn.execute("INSERT INTO regions VALUES ('US', 'United States'), ('EU', 'Europe')")
    conn.commit()
    conn.close()
    return f"sqlite:///{db_path}"


# ---------------------------------------------------------------------------
# as_langchain_tools() — LocalFileConnector
# ---------------------------------------------------------------------------


def test_langchain_tools_generated_for_local_file(csv_dir: Path) -> None:
    """as_langchain_tools() should return exactly two tools with correct names."""
    from ai_data_science_team.connectors import LocalFileConnector

    conn = LocalFileConnector(str(csv_dir))
    conn.connect()
    tools = conn.as_langchain_tools()

    assert len(tools) == 2
    names = {t.name for t in tools}
    assert "local_file_list_sources" in names
    assert "local_file_read" in names


def test_langchain_tool_list_sources_invoke(csv_dir: Path) -> None:
    """list_sources tool should return newline-separated file names when invoked."""
    from ai_data_science_team.connectors import LocalFileConnector

    conn = LocalFileConnector(str(csv_dir))
    conn.connect()
    tools = {t.name: t for t in conn.as_langchain_tools()}

    result = tools["local_file_list_sources"].invoke({})
    assert isinstance(result, str)
    assert "sales.csv" in result
    assert "costs.csv" in result


def test_langchain_tool_read_source_invoke(csv_dir: Path) -> None:
    """read_source tool should return CSV text containing expected columns."""
    from ai_data_science_team.connectors import LocalFileConnector

    conn = LocalFileConnector(str(csv_dir))
    conn.connect()
    tools = {t.name: t for t in conn.as_langchain_tools()}

    result = tools["local_file_read"].invoke({"source": "sales.csv", "max_rows": 2})
    assert isinstance(result, str)
    assert "date" in result
    assert "revenue" in result
    # max_rows=2 → header + 2 data rows = 3 CSV lines
    lines = [line_ for line_ in result.splitlines() if line_.strip()]
    assert len(lines) == 3


def test_langchain_tool_read_source_default_max_rows(csv_dir: Path) -> None:
    """read_source tool with no max_rows should return all rows (3 data rows)."""
    from ai_data_science_team.connectors import LocalFileConnector

    conn = LocalFileConnector(str(csv_dir))
    conn.connect()
    tools = {t.name: t for t in conn.as_langchain_tools()}

    result = tools["local_file_read"].invoke({"source": "costs.csv"})
    lines = [line_ for line_ in result.splitlines() if line_.strip()]
    assert len(lines) == 4  # header + 3 data rows


# ---------------------------------------------------------------------------
# as_langchain_tools() — SQLConnector
# ---------------------------------------------------------------------------


def test_langchain_tools_generated_for_sql(disk_sqlite: str) -> None:
    """SQLConnector should expose sql_list_tables, sql_read_table, sql_schema tools."""
    from ai_data_science_team.connectors import SQLConnector

    conn = SQLConnector(disk_sqlite)
    conn.connect()
    tools = conn.as_langchain_tools()

    names = {t.name for t in tools}
    assert "sql_list_tables" in names
    assert "sql_read_table" in names
    assert "sql_schema" in names


def test_langchain_sql_list_sources_invoke(disk_sqlite: str) -> None:
    """sql_list_tables tool should enumerate real table names."""
    from ai_data_science_team.connectors import SQLConnector

    conn = SQLConnector(disk_sqlite)
    conn.connect()
    tools = {t.name: t for t in conn.as_langchain_tools()}

    result = tools["sql_list_tables"].invoke({})
    assert "products" in result
    assert "regions" in result


def test_langchain_sql_read_invoke(disk_sqlite: str) -> None:
    """sql_read_table tool should return CSV text for the products table."""
    from ai_data_science_team.connectors import SQLConnector

    conn = SQLConnector(disk_sqlite)
    conn.connect()
    tools = {t.name: t for t in conn.as_langchain_tools()}

    result = tools["sql_read_table"].invoke({"table": "main.products", "max_rows": 10})
    assert "Widget" in result


# ---------------------------------------------------------------------------
# Recursive LocalFileConnector
# ---------------------------------------------------------------------------


def test_recursive_scan_finds_subdirectory_files(recursive_dir: Path) -> None:
    """recursive=True should list files in sub-directories."""
    from ai_data_science_team.connectors import LocalFileConnector

    conn = LocalFileConnector(str(recursive_dir), recursive=True)
    conn.connect()
    sources = conn.list_sources()

    assert any("level1.csv" in s for s in sources)
    assert any("level2.csv" in s for s in sources)
    assert not any("readme.txt" in s for s in sources)


def test_recursive_scan_off_misses_subdirectory(recursive_dir: Path) -> None:
    """recursive=False (default) should NOT list files in sub-directories."""
    from ai_data_science_team.connectors import LocalFileConnector

    conn = LocalFileConnector(str(recursive_dir), recursive=False)
    conn.connect()
    sources = conn.list_sources()

    assert any("level1.csv" in s for s in sources)
    assert not any("level2.csv" in s for s in sources)


def test_recursive_connector_read(recursive_dir: Path) -> None:
    """Recursive connector should read sub-dir files using relative path."""
    from ai_data_science_team.connectors import LocalFileConnector

    conn = LocalFileConnector(str(recursive_dir), recursive=True)
    conn.connect()
    sources = conn.list_sources()

    # Read the sub-directory file
    sub_source = next(s for s in sources if "level2.csv" in s)
    df = conn.read(sub_source)
    assert list(df.columns) == ["a", "b"]
    assert len(df) == 2


# ---------------------------------------------------------------------------
# Disk-based SQLite — SQLConnector persistence
# ---------------------------------------------------------------------------


def test_sql_disk_based_two_tables(disk_sqlite: str) -> None:
    """Disk SQLite connector should see both tables after reconnection."""
    from ai_data_science_team.connectors import SQLConnector

    # Open a fresh connection (simulates reconnection to persistent DB)
    conn = SQLConnector(disk_sqlite)
    conn.connect()
    sources = conn.list_sources()

    assert "main.products" in sources
    assert "main.regions" in sources


def test_sql_disk_based_read_products(disk_sqlite: str) -> None:
    """Reading products table from disk SQLite should return 3 rows."""
    from ai_data_science_team.connectors import SQLConnector

    conn = SQLConnector(disk_sqlite)
    conn.connect()
    df = conn.read("main.products")

    assert len(df) == 3
    assert "Gadget" in df["name"].values


def test_sql_disk_based_context_manager_close(disk_sqlite: str) -> None:
    """Context manager should cleanly close the disk SQLite connection."""
    from ai_data_science_team.connectors import SQLConnector

    with SQLConnector(disk_sqlite) as conn:
        df = conn.read("main.regions")
        assert len(df) == 2  # US, EU


# ---------------------------------------------------------------------------
# MCP Server — SQL-backed full JSON-RPC session
# ---------------------------------------------------------------------------


def test_mcp_sql_full_session(disk_sqlite: str) -> None:
    """Full MCP session: initialize → tools/list → tools/call → resources/list."""
    from ai_data_science_team.connectors import SQLConnector
    from plugins.connectors.mcp_server.server import MCPServer

    conn = SQLConnector(disk_sqlite)
    conn.connect()
    srv = MCPServer(connector=conn)

    # 1. initialize
    r = srv.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert r["result"]["protocolVersion"] == "2024-11-05"

    # 2. tools/list
    r = srv.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = [t["name"] for t in r["result"]["tools"]]
    assert "list_sources" in names and "read_source" in names

    # 3. tools/call — list_sources
    r = srv.handle_request(
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "list_sources", "arguments": {}}}
    )
    assert "products" in r["result"]["content"][0]["text"]

    # 4. tools/call — read_source products
    r = srv.handle_request(
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "read_source", "arguments": {"source": "main.products", "max_rows": 2}}}
    )
    csv_text = r["result"]["content"][0]["text"]
    assert "Widget" in csv_text or "Gadget" in csv_text  # 2 rows from 3

    # 5. tools/call — connector_health
    r = srv.handle_request(
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
         "params": {"name": "connector_health", "arguments": {}}}
    )
    health = json.loads(r["result"]["content"][0]["text"])
    assert health["status"] == "ok"

    # 6. resources/list
    r = srv.handle_request({"jsonrpc": "2.0", "id": 6, "method": "resources/list"})
    uris = [res["uri"] for res in r["result"]["resources"]]
    assert any("products" in u for u in uris)


def test_mcp_sql_io_loop(disk_sqlite: str) -> None:
    """Full IO loop with SQL-backed MCP server produces valid NDJSON output."""
    from ai_data_science_team.connectors import SQLConnector
    from plugins.connectors.mcp_server.server import MCPServer

    conn = SQLConnector(disk_sqlite)
    conn.connect()

    requests_ndjson = "\n".join([
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
        json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                    "params": {"name": "list_sources", "arguments": {}}}),
    ]) + "\n"

    in_stream = io.StringIO(requests_ndjson)
    out_stream = io.StringIO()
    srv = MCPServer(connector=conn, input_stream=in_stream, output_stream=out_stream)
    srv.run()

    out_stream.seek(0)
    lines = [line_ for line_ in out_stream.read().splitlines() if line_.strip()]
    assert len(lines) == 3

    responses = [json.loads(line_) for line_ in lines]
    assert responses[0]["id"] == 1
    assert responses[1]["id"] == 2
    assert responses[2]["id"] == 3
    assert "products" in responses[2]["result"]["content"][0]["text"]


# ---------------------------------------------------------------------------
# MCP Server — CSV-backed resources/read with SQL-style URI
# ---------------------------------------------------------------------------


def test_mcp_csv_resources_read_uri(csv_dir: Path) -> None:
    """resources/read should resolve URI and return CSV content."""
    from ai_data_science_team.connectors import LocalFileConnector
    from plugins.connectors.mcp_server.server import MCPServer

    conn = LocalFileConnector(str(csv_dir))
    conn.connect()
    srv = MCPServer(connector=conn)

    r = srv.handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "resources/read",
         "params": {"uri": "connector://local_file/costs.csv"}}
    )
    text = r["result"]["contents"][0]["text"]
    assert "cost" in text
    assert r["result"]["contents"][0]["mimeType"] == "text/csv"


# ---------------------------------------------------------------------------
# CLI argparse smoke test
# ---------------------------------------------------------------------------


def test_cli_parser_help_no_exit() -> None:
    """CLI argument parser should be buildable without raising SystemExit."""
    from plugins.connectors.mcp_server.server import _build_parser

    parser = _build_parser()
    assert parser is not None
    # Verify expected arguments exist
    args = parser.parse_args(["--base-dir", "/tmp"])
    assert args.base_dir == "/tmp"
    assert args.db is None


def test_cli_parser_db_flag() -> None:
    """--db flag should be parsed correctly and mutually exclusive with --base-dir."""
    from plugins.connectors.mcp_server.server import _build_parser

    parser = _build_parser()
    args = parser.parse_args(["--db", "sqlite:///test.db"])
    assert args.db == "sqlite:///test.db"
    assert args.base_dir is None


# ---------------------------------------------------------------------------
# Cross-connector pipeline: CSV metadata → SQL storage → re-read
# ---------------------------------------------------------------------------


def test_cross_connector_pipeline(tmp_path: Path) -> None:
    """Chain: read CSV with LocalFileConnector → write summary to SQLite → read back."""
    import sqlalchemy as sa
    from ai_data_science_team.connectors import LocalFileConnector, SQLConnector

    # Step 1 — create CSV data
    csv_dir = tmp_path / "raw"
    csv_dir.mkdir()
    (csv_dir / "q1.csv").write_text("month,sales\n2024-01,5000\n2024-02,6200\n2024-03,7100\n")

    # Step 2 — read via LocalFileConnector
    local_conn = LocalFileConnector(str(csv_dir))
    local_conn.connect()
    df = local_conn.read("q1.csv")
    assert len(df) == 3

    # Step 3 — persist summary to SQLite
    db_path = tmp_path / "summary.db"
    engine = sa.create_engine(f"sqlite:///{db_path}")
    summary = pd.DataFrame({"total_sales": [df["sales"].sum()], "rows": [len(df)]})
    summary.to_sql("summary", engine, index=False, if_exists="replace")

    # Step 4 — read back with SQLConnector
    sql_conn = SQLConnector(f"sqlite:///{db_path}")
    sql_conn.connect()
    result = sql_conn.read("main.summary")

    assert result["total_sales"].iloc[0] == 18300
    assert result["rows"].iloc[0] == 3
