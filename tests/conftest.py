from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTEST_TEMP_ROOT = REPO_ROOT / ".pytest-tmp"
PYTEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("PYTEST_DEBUG_TEMPROOT", str(PYTEST_TEMP_ROOT))


def pytest_configure(config: pytest.Config) -> None:
    if getattr(config.option, "basetemp", None):
        return
    base_temp = REPO_ROOT / ".pytest-work"
    base_temp.mkdir(parents=True, exist_ok=True)
    config.option.basetemp = str(base_temp)


@pytest.fixture(scope="function")
def tmp_path() -> Path:
    root = REPO_ROOT / ".tmp-tests"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"pytest-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
