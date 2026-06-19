"""Universal platform query and action control plane.

This package is intentionally independent from the DS/ML agent runtime.  It
catalogs platform resources, resolves authorized platform state, and plans or
executes governed platform actions.
"""

from platform_api.control_plane.catalog import get_platform_catalog

__all__ = ["get_platform_catalog"]
