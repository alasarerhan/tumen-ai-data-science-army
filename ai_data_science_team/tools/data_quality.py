"""Canonical ad: ``tools.data_quality``.

Modülün gerçek uygulaması ``quality.py``'de (B2 spec). Bu şim kanonik
``data_quality`` adını dışarıya sunar; ``from ai_data_science_team.tools.data_quality import *``
gibi kullanımlar (test_governance_insight_integration_real dahil) artık
ModuleNotFoundError üretmez.
"""

from ai_data_science_team.tools import quality as _impl
from ai_data_science_team.tools.quality import *  # noqa: F401, F403

# Gerçek uygulamanın aynı modül olduğunu belgeleyelim (identity testi).
__all__ = getattr(_impl, "__all__", [])
if not __all__:
    __all__ = [n for n in dir(_impl) if not n.startswith("_")]
