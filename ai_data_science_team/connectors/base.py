from __future__ import annotations

"""DataConnector — abstract base interface for all data source connectors (M11).

Every connector must implement five core methods:
    name            → unique identifier string
    connect()       → open/validate the connection
    list_sources()  → enumerate available tables / files / endpoints
    read()          → return a DataFrame for a given source
    health_check()  → return a status dict

Optional helper:
    as_langchain_tools() → LangChain @tool wrappers (default: auto-generated)

Usage example::

    class MyConnector(DataConnector):
        @property
        def name(self): return "my_source"

        def connect(self, **kw): ...
        def list_sources(self): return ["table_a"]
        def read(self, source, **kw): return pd.read_csv(...)
        def health_check(self): return {"status": "ok"}

    conn = MyConnector()
    conn.connect()
    df = conn.read("table_a")
"""
from abc import ABC, abstractmethod  # noqa: E402, F401
from typing import Any, Dict, List, Optional  # noqa: E402, F401

import pandas as pd  # noqa: E402, F401


class DataConnector(ABC):
    """Abstract base class for all data source connectors.

    Subclass this and implement the five abstract members to integrate any
    data source (files, databases, APIs, cloud storage, etc.) into the
    ai-data-science-team agent ecosystem.
    """

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique, machine-readable identifier for this connector, e.g. ``"csv_local"``."""

    @property
    def description(self) -> str:
        """Human-readable description shown to agents and MCP clients."""
        return f"DataConnector({self.name})"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    def connect(self, **kwargs: Any) -> None:
        """Open / validate the underlying connection.

        Raise ``ConnectionError`` if the connection cannot be established.
        Implementations should be idempotent (safe to call multiple times).
        """

    def close(self) -> None:
        """Close the underlying connection.  Override if cleanup is needed."""

    def __enter__(self) -> "DataConnector":
        self.connect()
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @abstractmethod
    def list_sources(self) -> List[str]:
        """Return a list of available source identifiers.

        For file connectors this is a list of file paths / names.
        For SQL connectors this is a list of ``schema.table`` strings.
        For API connectors this may be endpoint names.
        """

    # ------------------------------------------------------------------
    # Data access
    # ------------------------------------------------------------------

    @abstractmethod
    def read(
        self,
        source: str,
        *,
        max_rows: Optional[int] = None,
        columns: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Read *source* and return a ``pandas.DataFrame``.

        Parameters
        ----------
        source:
            One of the identifiers returned by :meth:`list_sources`.
        max_rows:
            If provided, limit the number of rows returned.
        columns:
            If provided, return only these columns.
        **kwargs:
            Connector-specific read options.
        """

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Return a status dictionary.

        At minimum include:
            ``{"status": "ok" | "error", "connector": self.name}``
        """

    # ------------------------------------------------------------------
    # LangChain integration
    # ------------------------------------------------------------------

    def as_langchain_tools(self) -> list:
        """Return a list of LangChain ``@tool``-decorated callables.

        The default implementation generates two tools:
        ``{name}_list_sources`` and ``{name}_read``.
        Override to provide richer docstrings or additional tools.
        """
        from langchain.tools import tool as lc_tool  # noqa: E402, F401

        connector = self  # capture for closures

        @lc_tool
        def list_sources() -> str:
            """List available data sources for this connector."""
            sources = connector.list_sources()
            return "\n".join(sources) if sources else "(no sources found)"

        list_sources.name = f"{self.name}_list_sources"  # type: ignore[attr-defined]

        @lc_tool
        def read_source(source: str, max_rows: int = 1000) -> str:
            """Read a data source and return a preview as CSV text."""
            df = connector.read(source, max_rows=max_rows)
            return df.to_csv(index=False)

        read_source.name = f"{self.name}_read"  # type: ignore[attr-defined]

        return [list_sources, read_source]

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"<{type(self).__name__} name={self.name!r}>"
