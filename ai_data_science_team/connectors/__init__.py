"""ai_data_science_team.connectors — DataConnector interface and built-in implementations (M11).

Public API
----------
DataConnector          Abstract base class for all connectors.
LocalFileConnector     Read local CSV / Excel / Parquet / JSON files.
SQLConnector           Read tables from any SQLAlchemy-supported database.

Plugin discovery
----------------
Third-party connectors can register themselves via the
``ai_data_science_team.connectors`` entry-point group in their ``pyproject.toml``::

    [project.entry-points."ai_data_science_team.connectors"]
    my_connector = "my_package.connector:MyConnector"

Registered connectors are loaded lazily via :func:`load_connector_plugins`.

Example
-------
>>> from ai_data_science_team.connectors import LocalFileConnector
>>> conn = LocalFileConnector("/data/raw")
>>> conn.connect()
>>> df = conn.read("sales.csv", max_rows=100)
"""

from ai_data_science_team.connectors.base import DataConnector
from ai_data_science_team.connectors.local_file_connector import LocalFileConnector
from ai_data_science_team.connectors.sql_connector import SQLConnector

__all__ = [
    "DataConnector",
    "LocalFileConnector",
    "SQLConnector",
    "load_connector_plugins",
]


def load_connector_plugins() -> dict[str, type]:
    """Discover and return connector classes registered via entry-points.

    Returns a ``{name: class}`` mapping.  Only available in Python ≥ 3.12
    with ``importlib.metadata``; silently returns ``{}`` on older runtimes
    or if no plugins are installed.
    """
    try:
        from importlib.metadata import entry_points
        eps = entry_points(group="ai_data_science_team.connectors")
        return {ep.name: ep.load() for ep in eps}
    except Exception:
        return {}
