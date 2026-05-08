from __future__ import annotations

import asyncio
import logging
import signal
import threading
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from platform_api.core.config import settings
from platform_api.core.observability import configure_logging
from platform_api.orchestration.agent_catalog import register_production_agent_catalog
from platform_api.orchestration.runtime_state import validate_runtime_state_settings
from platform_api.services.run_orchestration_service import validate_orchestration_runtime_settings

logger = logging.getLogger(__name__)

_scheduler = None
_scheduler_lock = threading.Lock()
_shutdown_event = asyncio.Event()
SCHEDULER_ENABLED_STATE_KEY = "scheduler_runtime_enabled"


def _register_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    def signal_handler(sig, frame):
        logger.info("Received signal %s, initiating graceful shutdown", sig)
        _shutdown_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s, None))
        except (NotImplementedError, RuntimeError):
            logger.debug("Signal handlers are unavailable on this event loop")
            break


def enable_runtime_services(app: FastAPI, *, scheduler: bool = True) -> FastAPI:
    """Enable runtime-only services for deployed ASGI applications."""
    app.state.scheduler_runtime_enabled = scheduler
    return app


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown."""
    global _scheduler

    loop = asyncio.get_event_loop()
    _register_signal_handlers(loop)

    logger.info("Application starting up...")
    configure_logging()
    validate_orchestration_runtime_settings(raise_runtime=True)
    validate_runtime_state_settings(raise_runtime=True)
    app.state.agent_catalog_registration = register_production_agent_catalog()

    try:
        settings.validate_directories()
        logger.info("Directory validation passed")
    except RuntimeError as e:
        logger.error("CRITICAL: Directory validation failed: %s", e)
        raise

    if getattr(app.state, SCHEDULER_ENABLED_STATE_KEY, False):
        try:
            from platform_api.db.session import get_db
            from platform_api.services.scheduler_service import create_default_scheduler

            db = next(get_db())
            with _scheduler_lock:
                if _scheduler is None:
                    _scheduler = create_default_scheduler(db)
            await _scheduler.start()
            logger.info("Scheduler started successfully")

        except Exception as e:
            logger.error(
                "CRITICAL: Could not start scheduler - background jobs will not run. Error: %s",
                e,
            )
            with _scheduler_lock:
                if _scheduler:
                    try:
                        await _scheduler.stop()
                    except Exception as stop_err:
                        logger.error("Error stopping scheduler during cleanup: %s", stop_err)
                _scheduler = None
    else:
        logger.info("Scheduler startup skipped for app factory instance")

    try:
        yield
    finally:
        logger.info("Application shutting down...")

        with _scheduler_lock:
            scheduler = _scheduler
            _scheduler = None

        if scheduler:
            logger.info("Stopping scheduler...")
            try:
                await scheduler.stop()
                logger.info("Scheduler stopped")
            except Exception as e:
                logger.error("Error stopping scheduler: %s", e)

        await asyncio.sleep(0.5)
        logger.info("Shutdown complete")
