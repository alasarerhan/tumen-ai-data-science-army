from __future__ import annotations

from platform_api.main import create_app
from platform_api.runtime import enable_runtime_services

app = enable_runtime_services(create_app())
