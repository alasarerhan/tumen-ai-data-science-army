"""pytest conftest for the ai-data-science-team package tests.

The top-level ai_data_science_team/__init__.py imports all agents which
require langchain_openai, langchain_experimental, etc.  For connector + MCP
+ time-series tests those heavy deps are not always installed.  We stub the
package-level module so Python skips that __init__ while still loading
individual sub-packages (connectors, tools, ml_agents) correctly.
"""
import sys
import types
from pathlib import Path

# Resolve the real repository root:
# plugins/tests/conftest.py -> plugins/tests -> plugins -> repo root
_repo_root = Path(__file__).resolve().parents[2]

# Load .env from repo root (OPENAI_API_KEY, etc.) — safe no-op if file absent
try:
    from dotenv import load_dotenv
    load_dotenv(_repo_root / ".env", override=False)
except ImportError:
    pass

# Always make repo root and plugins dir importable
for p in (_repo_root, _repo_root / "plugins"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Stub ai_data_science_team as a namespace-only package if the full
# __init__ would fail (e.g. missing langchain_openai / langchain_experimental)
if "ai_data_science_team" not in sys.modules:
    try:
        # Try a lightweight import to see if the full package is loadable
        import importlib
        importlib.import_module("ai_data_science_team")
    except (ImportError, Exception):
        _pkg = types.ModuleType("ai_data_science_team")
        _pkg.__path__ = [str(_repo_root / "ai_data_science_team")]  # type: ignore[attr-defined]
        _pkg.__package__ = "ai_data_science_team"
        _pkg.__spec__ = None  # type: ignore[assignment]
        sys.modules["ai_data_science_team"] = _pkg
