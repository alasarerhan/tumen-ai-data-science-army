"""Canonical ad: ``tools.model_monitoring``.

Modülün gerçek uygulaması ``modelops.py``'de (K2 spec). Bu şim kanonik
``model_monitoring`` adını dışarıya sunar; ``from
ai_data_science_team.tools.model_monitoring import *`` artık
ModuleNotFoundError üretmez.
"""

from ai_data_science_team.tools import modelops as _impl
from ai_data_science_team.tools.modelops import *  # noqa: F401, F403

__all__ = getattr(_impl, "__all__", [])
if not __all__:
    __all__ = [n for n in dir(_impl) if not n.startswith("_")]
