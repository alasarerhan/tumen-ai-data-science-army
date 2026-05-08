from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import event
from sqlalchemy.engine import Engine


def sqlite_now() -> str:
    # Legacy SQLite schemas may still reference `now()` as server default.
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def register_sqlite_compat_functions(target_engine: Engine) -> None:
    if target_engine.dialect.name != "sqlite":
        return

    @event.listens_for(target_engine, "connect")
    def _register_now_function(dbapi_connection, _connection_record) -> None:
        dbapi_connection.create_function("now", 0, sqlite_now)
