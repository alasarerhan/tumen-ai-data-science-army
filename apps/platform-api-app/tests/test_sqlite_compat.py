from __future__ import annotations

from sqlalchemy import create_engine, text

from platform_api.db.sqlite_compat import register_sqlite_compat_functions


def test_register_sqlite_now_function() -> None:
    engine = create_engine("sqlite:///:memory:")
    register_sqlite_compat_functions(engine)

    with engine.connect() as conn:
        value = conn.execute(text("SELECT now()")).scalar_one()

    assert isinstance(value, str)
    assert value != ""
