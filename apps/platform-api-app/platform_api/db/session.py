from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from platform_api.core.config import settings
from platform_api.db.sqlite_compat import register_sqlite_compat_functions
from platform_api.tenant_context import clear_tenant_context, configure_session_events

logger = logging.getLogger(__name__)


_POOL_SIZE = 20
_MAX_OVERFLOW = 30
_POOL_RECYCLE_SECONDS = 1800
_POOL_TIMEOUT_SECONDS = 30


def _is_postgresql(url: str) -> bool:
    return url.startswith("postgresql")


_engine_kwargs = {
    "pool_pre_ping": True,
}

if _is_postgresql(settings.database_url):
    _engine_kwargs["pool_size"] = _POOL_SIZE
    _engine_kwargs["max_overflow"] = _MAX_OVERFLOW
    _engine_kwargs["pool_recycle"] = _POOL_RECYCLE_SECONDS
    _engine_kwargs["pool_timeout"] = _POOL_TIMEOUT_SECONDS


engine = create_engine(settings.database_url, **_engine_kwargs)
register_sqlite_compat_functions(engine)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
configure_session_events(SessionLocal)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error("Database session error, rolling back: %s", e)
        db.rollback()
        raise
    finally:
        clear_tenant_context()
        db.close()


@contextmanager
def atomic_transaction(db: Session) -> Generator[Session, None, None]:
    """Context manager for atomic database transactions.
    
    Automatically commits on success, rolls back on exception.
    
    Usage:
        with atomic_transaction(db) as session:
            session.add(obj)
            # Automatically commits on exit, rolls back on exception
    """
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error("Transaction failed, rolling back: %s", e)
        db.rollback()
        raise
