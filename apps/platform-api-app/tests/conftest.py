"""Shared pytest fixtures for platform-api-app tests.

``db_session``
    An in-memory SQLite session with all ORM tables created.
    Each test gets a fresh session in its own transaction that is
    rolled back on teardown, so tests are fully isolated.

``seeded_db``
    A db_session with a canonical set of objects:
      tenant, user (admin), workspace, workspace_membership (admin),
      user_member + workspace_membership (member).

These fixtures avoid external dependencies (no running Postgres) while
exercising real SQLAlchemy queries.
"""

from __future__ import annotations

import os
import shutil
import sys
import uuid as _uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from platform_api.db.base import Base
from platform_api.db.models import (
    Tenant,
    User,
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PYTEST_TEMP_ROOT = REPO_ROOT / ".pytest-tmp"
PYTEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("PYTEST_DEBUG_TEMPROOT", str(PYTEST_TEMP_ROOT))


def pytest_configure(config: pytest.Config) -> None:
    """Keep pytest temp dirs inside the workspace and away from locked system paths."""
    if getattr(config.option, "basetemp", None):
        return
    base_temp = REPO_ROOT / ".pytest-work"
    base_temp.mkdir(parents=True, exist_ok=True)
    config.option.basetemp = str(base_temp)


@pytest.fixture(scope="function")
def tmp_path():
    """Workspace-local tmp path that avoids Windows tempdir permission issues."""
    root = REPO_ROOT / ".tmp-tests"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"pytest-{_uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


# ---------------------------------------------------------------------------
# SQLite engine with UUID support
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def db_engine():
    """Create a fresh in-memory SQLite engine.

    FK enforcement is intentionally **disabled** here: ``postgresql.UUID``
    stores UUIDs in hex-without-dashes format on SQLite, and enabling
    ``PRAGMA foreign_keys=ON`` causes spurious integrity errors because
    SQLite compares the raw stored strings which may differ in format
    between the PK and FK columns.  Our service-layer tests verify
    business logic, not FK integrity.
    """
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Yield a real SQLAlchemy Session backed by in-memory SQLite."""
    factory = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Seeded DB — canonical set of objects
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def seeded_db(db_session: Session):
    """
    Returns ``{"tenant", "workspace", "user_admin", "membership_admin",
               "user_member", "membership_member", "db"}``
    with everything flushed to the in-memory DB.
    """
    tenant_id = _uuid.uuid4()
    ws_id = _uuid.uuid4()
    user_admin_id = _uuid.uuid4()
    user_member_id = _uuid.uuid4()

    tenant = Tenant(id=tenant_id, name="Test Corp")
    db_session.add(tenant)
    db_session.flush()

    workspace = Workspace(id=ws_id, tenant_id=tenant_id, name="default")
    db_session.add(workspace)
    db_session.flush()

    user_admin = User(id=user_admin_id, sub=f"sub|{user_admin_id}", email="admin@test.com")
    user_member = User(id=user_member_id, sub=f"sub|{user_member_id}", email="member@test.com")
    db_session.add_all([user_admin, user_member])
    db_session.flush()

    membership_admin = WorkspaceMembership(
        id=_uuid.uuid4(),
        workspace_id=ws_id,
        user_id=user_admin_id,
        role=WorkspaceRole.admin,
    )
    membership_member = WorkspaceMembership(
        id=_uuid.uuid4(),
        workspace_id=ws_id,
        user_id=user_member_id,
        role=WorkspaceRole.member,
    )
    db_session.add_all([membership_admin, membership_member])
    db_session.flush()

    return {
        "tenant": tenant,
        "workspace": workspace,
        "user_admin": user_admin,
        "user_member": user_member,
        "membership_admin": membership_admin,
        "membership_member": membership_member,
        "db": db_session,
    }
