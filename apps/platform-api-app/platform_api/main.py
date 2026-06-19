from __future__ import annotations

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from platform_api.core.config import settings
from platform_api.core.csrf import CsrfProtectionMiddleware
from platform_api.core.idempotency import IdempotencyMiddleware
from platform_api.core.observability import configure_logging, setup_observability
from platform_api.core.rate_limit import RateLimitMiddleware
from platform_api.core.request_size_limit import RequestSizeLimitMiddleware
from platform_api.runtime import lifespan
from platform_api.routes.admin import router as admin_router
from platform_api.routes.artifacts import router as artifacts_router
from platform_api.routes.auth import router as auth_router
from platform_api.routes.chat import router as chat_router
from platform_api.routes.control_plane import router as control_plane_router
from platform_api.routes.data_sources import router as data_sources_router
from platform_api.routes.discovery import router as discovery_router
from platform_api.routes.errors import router as errors_router
from platform_api.routes.finops import router as finops_router
from platform_api.routes.health import router as health_router
from platform_api.routes.hitl import router as hitl_router
from platform_api.routes.logs import router as logs_router
from platform_api.routes.me import router as me_router
from platform_api.routes.modelops import router as modelops_router
from platform_api.routes.prefect import router as prefect_router
from platform_api.routes.provisioning import router as provisioning_router
from platform_api.routes.run_signals import router as run_signals_router
from platform_api.routes.runs import router as runs_router
from platform_api.routes.scheduler import router as scheduler_router
from platform_api.routes.strategy import router as strategy_router
from platform_api.routes.versioning import router as versioning_router
from platform_api.routes.workflows import router as workflows_router
from platform_api.routes.workflow_node_types import router as workflow_node_types_router

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    MIDDLEWARE ORDER (CRITICAL)
    ---------------------------
    Middleware is executed in REVERSE order of registration (LIFO).
    The last middleware added is the first to process the request.

    Current order (request flow):
     1. CORSMiddleware - Handle CORS preflight
     2. IdempotencyMiddleware - Return cached responses for duplicate idempotency keys
     3. CsrfProtectionMiddleware - Validate CSRF tokens for mutations
     4. RateLimitMiddleware - Enforce rate limits
     5. RequestSizeLimitMiddleware - Reject oversized requests
     6. GZipMiddleware - Compress responses
     7. metrics_and_logging_middleware (from setup_observability) - Log & metrics

    IMPORTANT: The observability middleware (added in setup_observability) reads
    tenant context from ContextVars. If auth middleware is added, it MUST be
    registered AFTER setup_observability() so that tenant context is set before
    the observability middleware logs the request.

    Example of correct auth middleware registration:
        setup_observability(app)  # Adds metrics middleware
        app.add_middleware(AuthMiddleware)  # Sets tenant context
        # Now metrics middleware can log tenant_id

    WARNING: Do not change middleware order without understanding the
    dependencies between them. Incorrect order can cause:
    - Missing tenant_id in audit logs
    - Rate limiting not applied to authenticated requests
    - CORS failures on authenticated endpoints
    """
    configure_logging()
    app = FastAPI(title="Platform API", version="0.1.0", lifespan=lifespan)
    setup_observability(app)
    _register_middlewares(app)
    _register_routers(app)
    return app


def _register_middlewares(app: FastAPI) -> None:
    app.add_middleware(
        GZipMiddleware,
        minimum_size=1000,
        compresslevel=6,
    )

    app.add_middleware(
        RequestSizeLimitMiddleware,
        max_body_bytes=10 * 1024 * 1024,
        route_limits=[
            ("/v1/chat/sessions/", settings.chat_upload_max_mb * 1024 * 1024 + 1024),
        ],
    )

    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=120,
        redis_url=settings.agent_cache_redis_url or None,
    )

    app.add_middleware(CsrfProtectionMiddleware)

    app.add_middleware(
        IdempotencyMiddleware,
        redis_url=settings.agent_cache_redis_url or None,
    )

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-User-Id", "X-Request-Id", "If-Match"],
    )


def _register_routers(app: FastAPI) -> None:
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(me_router)
    app.include_router(prefect_router)
    app.include_router(provisioning_router)
    app.include_router(runs_router)
    app.include_router(artifacts_router)
    app.include_router(workflows_router)
    app.include_router(workflow_node_types_router)
    app.include_router(strategy_router)
    app.include_router(logs_router)
    app.include_router(data_sources_router)
    app.include_router(modelops_router)
    app.include_router(hitl_router)
    app.include_router(chat_router)
    app.include_router(control_plane_router)
    app.include_router(errors_router)
    app.include_router(run_signals_router)
    app.include_router(finops_router)
    app.include_router(admin_router)
    app.include_router(scheduler_router)
    app.include_router(versioning_router)
    app.include_router(discovery_router)
