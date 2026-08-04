"""pytest conftest for the top-level tests/ directory.

Two responsibilities:
  1. Force pytest to import the MODERNIZED ai_data_science_team package
     (tools/bayesian.py, etc.) instead of the legacy top-level package
     which has none of the renamed tool symbols.
  2. Provide the original tmp_path / basetemp / ' 2.py' ignore fixtures.
"""

from __future__ import annotations

import os
import shutil
import sys
import types
import uuid
from pathlib import Path

import pytest

# ---------------------------------------------------------------------
# Modernized-package stub (see ai_data_science_team/plugins/tests/conftest.py
# for the equivalent logic).
# ---------------------------------------------------------------------
# tests/conftest.py -> tests -> ai_data_science_team
_NESTED_PKG = Path(__file__).resolve().parents[1] / "ai_data_science_team"

# Make the modernized package + repo root importable.
sys.path.insert(0, str(_NESTED_PKG))
sys.path.insert(0, str(_NESTED_PKG.parent))

# Stub ai_data_science_team to the modernized nested dir so submodule
# imports (e.g. ai_data_science_team.tools.bayesian) resolve to the
# renamed tool files, not the legacy compat stubs.
_pkg = types.ModuleType("ai_data_science_team")
_pkg.__path__ = [str(_NESTED_PKG)]  # type: ignore[attr-defined]
_pkg.__package__ = "ai_data_science_team"
_pkg.__spec__ = None  # type: ignore[assignment]
sys.modules["ai_data_science_team"] = _pkg

# ---------------------------------------------------------------------
# Original fixtures + ignore list.
# ---------------------------------------------------------------------
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


def pytest_ignore_collect(collection_path, config):
    """Skip legacy ``... 2.py`` duplicate test files.

    The repo carries historic duplicates with a trailing space + ``2.py``
    suffix that pre-date the modernized package layout.  These files
    have stale references and would crash collection.  They are
    intentionally kept out of the test set until the duplicate-cleanup
    task removes them from the working tree.
    """
    return " 2.py" in str(collection_path)
