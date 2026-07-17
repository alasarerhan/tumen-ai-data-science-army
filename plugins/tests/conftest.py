"""pytest conftest for the ai-data-science-team package tests.

The repo has two parallel ai_data_science_team trees:

  <repo_root>/
    ai_data_science_team/                     <-- legacy / compat (a few files only)
      ai_data_science_team/                  <-- modernized (has the spec tools)
        tools/   agents/   templates/   ...
      plugins/                              <-- external packages (this dir)
        connectors/   tests/   ...

We force pytest to import the modernized nested package by stubbing
`ai_data_science_team` in sys.modules and pointing its `__path__` at the
nested dir. We also add the legacy `ai_data_science_team` (for plugins
subpackages) and the repo root (for .env loading).
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

# plugins/tests/conftest.py -> plugins/tests -> plugins -> ai_data_science_team
# _repo_root is `ai_data_science_team/`
# The modernized nested package lives at `_repo_root/ai_data_science_team/`.
# The legacy plugins/ dir is at `_repo_root/plugins/`.
_REPO_ROOT = Path(__file__).resolve().parents[2]  # = ai_data_science_team/
_NESTED_PKG = _REPO_ROOT / "ai_data_science_team"
_PLUGINS_DIR = _REPO_ROOT / "plugins"

# Load .env from the actual repo root (parent of ai_data_science_team/).
try:
    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT.parent / ".env", override=False)
except ImportError:
    pass

# Always make key paths importable.
for p in (_REPO_ROOT.parent, _REPO_ROOT, _PLUGINS_DIR, _PLUGINS_DIR / "tests", _NESTED_PKG):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

# Stub ai_data_science_team as a namespace package pointing at the
# modernized nested dir. We also include the plugins dir in __path__ so
# that `ai_data_science_team.plugins.*` resolves to the sibling plugins/.
_pkg = types.ModuleType("ai_data_science_team")
_pkg.__path__ = [
    str(_NESTED_PKG),      # modernized — put FIRST so submodules are picked
                            # from the nested dir, not the legacy.
    str(_REPO_ROOT),       # legacy (for ai_data_science_team.plugins, etc.)
]  # type: ignore[attr-defined]
_pkg.__package__ = "ai_data_science_team"
_pkg.__spec__ = None  # type: ignore[assignment]
sys.modules["ai_data_science_team"] = _pkg
