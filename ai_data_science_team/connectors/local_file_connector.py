"""LocalFileConnector — DataConnector implementation for local file-system sources (M11).

Supported formats: CSV, TSV, Excel (.xlsx/.xls), Parquet, JSON.
Wraps the existing ``ai_data_science_team.tools.data_loader`` helpers internally so
that agents can reference the same logic through the unified DataConnector interface
OR through the legacy @tool functions — both paths remain valid.

Example::

    conn = LocalFileConnector(base_dir="/data/raw")
    conn.connect()
    sources = conn.list_sources()          # ["sales.csv", "inventory.parquet", ...]
    df = conn.read("sales.csv", max_rows=500)
    logger.info(conn.health_check())
"""
from __future__ import annotations



import logging

logger = logging.getLogger(__name__)
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from ai_data_science_team.connectors.base import DataConnector

_SUPPORTED_EXTENSIONS = {".csv", ".tsv", ".xlsx", ".xls", ".parquet", ".json"}


class LocalFileConnector(DataConnector):
    """Read local tabular files as DataFrames.

    Parameters
    ----------
    base_dir:
        Root directory to scan for data files.  Defaults to ``os.getcwd()``.
    recursive:
        If ``True``, scan sub-directories as well.
    file_type:
        Optional extension filter, e.g. ``"csv"``.  If ``None``, all
        supported extensions are returned.
    """

    def __init__(
        self,
        base_dir: Optional[str] = None,
        *,
        recursive: bool = False,
        file_type: Optional[str] = None,
    ) -> None:
        self._base_dir: Path = Path(base_dir or os.getcwd()).expanduser().resolve()
        self._recursive = recursive
        self._file_type = f".{file_type.lstrip('.')}" if file_type else None
        self._connected = False

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "local_file"

    @property
    def description(self) -> str:
        return (
            f"LocalFileConnector reading from {self._base_dir} "
            f"(recursive={self._recursive})"
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self, **_: Any) -> None:
        if not self._base_dir.is_dir():
            raise ConnectionError(
                f"LocalFileConnector: base_dir does not exist: {self._base_dir}"
            )
        self._connected = True

    def close(self) -> None:
        self._connected = False

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_sources(self) -> List[str]:
        self._ensure_connected()
        paths: List[Path] = []
        iterator = self._base_dir.rglob("*") if self._recursive else self._base_dir.iterdir()
        for p in sorted(iterator):
            if not p.is_file():
                continue
            ext = p.suffix.lower()
            if self._file_type and ext != self._file_type:
                continue
            if ext not in _SUPPORTED_EXTENSIONS:
                continue
            try:
                relative = p.relative_to(self._base_dir)
            except ValueError:
                relative = p
            paths.append(relative)
        return [str(p) for p in paths]

    # ------------------------------------------------------------------
    # Data access
    # ------------------------------------------------------------------

    def read(
        self,
        source: str,
        *,
        max_rows: Optional[int] = None,
        columns: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        self._ensure_connected()
        full_path = self._base_dir / source
        if not full_path.exists():
            raise FileNotFoundError(f"Source not found: {full_path}")

        ext = full_path.suffix.lower()
        nrows = kwargs.pop("nrows", max_rows)

        if ext == ".csv":
            df = pd.read_csv(full_path, nrows=nrows, usecols=columns, **kwargs)
        elif ext == ".tsv":
            df = pd.read_csv(full_path, sep="\t", nrows=nrows, usecols=columns, **kwargs)
        elif ext in {".xlsx", ".xls"}:
            df = pd.read_excel(full_path, nrows=nrows, usecols=columns, **kwargs)
        elif ext == ".parquet":
            df = pd.read_parquet(full_path, columns=columns, **kwargs)
            if max_rows is not None:
                df = df.head(max_rows)
        elif ext == ".json":
            df = pd.read_json(full_path, **kwargs)
            if max_rows is not None:
                df = df.head(max_rows)
            if columns:
                df = df[columns]
        else:
            raise ValueError(f"Unsupported file extension: {ext}")

        return df

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        status = "ok" if self._connected and self._base_dir.is_dir() else "error"
        return {
            "connector": self.name,
            "status": status,
            "base_dir": str(self._base_dir),
            "exists": self._base_dir.is_dir(),
            "source_count": len(self.list_sources()) if status == "ok" else None,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_connected(self) -> None:
        if not self._connected:
            self.connect()
