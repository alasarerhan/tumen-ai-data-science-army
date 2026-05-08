"""Observability — structured logging + Prometheus metrics (M7).

SLO Budget (initial targets):
  HTTP p99 latency   < 500 ms     (SLO_LATENCY_P99_MS)
  HTTP error rate    < 1 %        (SLO_ERROR_RATE_BUDGET)
  Availability       99.5 %       (SLO_AVAILABILITY_BUDGET)

Metrics exposed at GET /metrics (prometheus text format):
  platform_api_http_requests_total{method, path, status}   Counter
  platform_api_http_request_duration_seconds{method, path} Histogram (buckets: 50ms..10s)
  platform_api_http_requests_in_flight                     Gauge

Security: Tenant context is included in structured logs for audit trail.
Best practice reference: https://agnitestudio.com/blog/preventing-cross-tenant-leakage/

FinOps: Configurable log retention to prevent unbounded storage growth.
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
import re
import time
import uuid
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from platform_api.tenant_context import get_current_tenant_id, get_current_workspace_id

# ---------------------------------------------------------------------------
# SLO constants (document the budget; alerting thresholds reference these)
# ---------------------------------------------------------------------------

SLO_LATENCY_P99_MS: int = 500          # 500 ms p99 target
SLO_ERROR_RATE_BUDGET: float = 0.01    # 1 % error rate budget  (5xx / total)
SLO_AVAILABILITY_BUDGET: float = 0.995 # 99.5 % availability

# ---------------------------------------------------------------------------
# Prometheus metric registry
# ---------------------------------------------------------------------------
#
# Using the default REGISTRY so metrics are accessible globally.
# Tests that need isolation should create their own CollectorRegistry.

_REGISTRY = CollectorRegistry(auto_describe=True)
_REGISTERED_COLLECTORS: set[str] = set()

HTTP_REQUESTS_TOTAL = Counter(
    "platform_api_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
    registry=_REGISTRY,
)

HTTP_REQUEST_DURATION = Histogram(
    "platform_api_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=_REGISTRY,
)

HTTP_REQUESTS_IN_FLIGHT = Gauge(
    "platform_api_http_requests_in_flight",
    "HTTP requests currently being processed",
    registry=_REGISTRY,
)


# ---------------------------------------------------------------------------
# Structured JSON logging
# ---------------------------------------------------------------------------


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line with standard fields."""

    _SEVERITY_MAP = {
        logging.DEBUG: "DEBUG",
        logging.INFO: "INFO",
        logging.WARNING: "WARNING",
        logging.ERROR: "ERROR",
        logging.CRITICAL: "CRITICAL",
    }
    _BEARER_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9\-\._~\+/]+=*")
    _COOKIE_TOKEN_PATTERN = re.compile(r"(access_token|refresh_token|csrf_token)=([^;,\s]+)")

    @classmethod
    def _redact_sensitive(cls, text: str) -> str:
        redacted = cls._BEARER_PATTERN.sub("Bearer [REDACTED]", text)
        redacted = cls._COOKIE_TOKEN_PATTERN.sub(r"\1=[REDACTED]", redacted)
        return redacted

    def format(self, record: logging.LogRecord) -> str:
        message = self._redact_sensitive(record.getMessage())
        payload: dict = {
            "severity": self._SEVERITY_MAP.get(record.levelno, "INFO"),
            "service": "platform-api",
            "logger": record.name,
            "message": message,
        }
        # If the message itself is valid JSON, merge it (used by request middleware).
        try:
            msg_dict = json.loads(message)
            if isinstance(msg_dict, dict):
                payload.update(msg_dict)
                payload.setdefault("message", payload.get("event", ""))
        except (json.JSONDecodeError, TypeError):
            pass

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def configure_logging() -> None:
    """Configure root logger with JSON output and file rotation.

    FinOps: Uses RotatingFileHandler with configurable retention to prevent
    unbounded log storage growth.

    Raises
    ------
    RuntimeError
        If log directory cannot be created or is not writable.
    """
    from platform_api.core.config import settings

    formatter = _JsonFormatter()

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)

    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(formatter)
    root.addHandler(stdout_handler)

    log_dir = Path(os.environ.get("PLATFORM_LOG_DIR", "./logs"))
    log_file = log_dir / "platform-api.json"

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        if not os.access(log_dir, os.W_OK):
            raise RuntimeError(
                f"Log directory {log_dir} is not writable. "
                f"Set PLATFORM_LOG_DIR environment variable to a writable directory."
            )
    except PermissionError as e:
        raise RuntimeError(
            f"Cannot create log directory {log_dir}: {e}. "
            f"Set PLATFORM_LOG_DIR environment variable to a writable directory."
        ) from e

    retention_days = settings.log_retention_days
    max_bytes = 100 * 1024 * 1024
    backup_count = max(1, retention_days)

    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
        root.info("File logging configured at %s (retention=%d days)", log_file, retention_days)
    except Exception as e:
        root.warning(
            "CRITICAL: Could not configure file logging at %s: %s. "
            "Logs will only go to stdout. Audit trail may be incomplete.",
            log_file, e,
        )

    for noisy in ("uvicorn.access", "watchfiles"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# FastAPI middleware + /metrics endpoint
# ---------------------------------------------------------------------------


def setup_observability(app: FastAPI) -> None:
    """Attach request metrics middleware and expose /metrics endpoint.

    Also registers metrics from:
    - Outbox service (queue depth, DLQ)
    - Scheduler service (jobs, leader status)
    - Memory monitor (process memory)
    - Workflow scheduler (schedules, triggers)
    """
    if getattr(app.state, "observability_configured", False):
        return

    logger = logging.getLogger("platform_api.request")

    _register_service_metrics()

    @app.middleware("http")
    async def metrics_and_logging_middleware(request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        method = request.method
        path = _normalise_path(request.url.path)

        HTTP_REQUESTS_IN_FLIGHT.inc()
        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception:
            HTTP_REQUESTS_IN_FLIGHT.dec()
            raise

        elapsed = time.perf_counter() - start
        elapsed_ms = round(elapsed * 1000, 2)
        status = str(response.status_code)

        HTTP_REQUESTS_IN_FLIGHT.dec()
        HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=status).inc()
        HTTP_REQUEST_DURATION.labels(method=method, path=path).observe(elapsed)

        response.headers["x-request-id"] = request_id

        tenant_id = get_current_tenant_id()
        workspace_id = get_current_workspace_id()

        log_payload = {
            "event": "http_request",
            "request_id": request_id,
            "method": method,
            "path": path,
            "status_code": response.status_code,
            "duration_ms": elapsed_ms,
            "slo_breach": elapsed_ms > SLO_LATENCY_P99_MS,
        }

        if tenant_id is not None:
            log_payload["tenant_id"] = str(tenant_id)
        if workspace_id is not None:
            log_payload["workspace_id"] = str(workspace_id)

        logger.info(json.dumps(log_payload))
        return response

    @app.get("/metrics", include_in_schema=False)
    async def prometheus_metrics() -> Response:
        """Expose Prometheus metrics in text format."""
        data = generate_latest(_REGISTRY)
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)

    app.state.observability_configured = True


def _register_metric_collector(collector) -> None:
    name = getattr(collector, "_name", repr(collector))
    if name in _REGISTERED_COLLECTORS:
        return
    _REGISTRY.register(collector)
    _REGISTERED_COLLECTORS.add(name)


def _register_service_metrics() -> None:
    """Register metrics from all services with the global registry."""
    try:
        from platform_api.services.outbox import (
            OUTBOX_DLQ_GAUGE,
            OUTBOX_FAILED_GAUGE,
            OUTBOX_PENDING_GAUGE,
            OUTBOX_PROCESSING_GAUGE,
        )
        _register_metric_collector(OUTBOX_PENDING_GAUGE)
        _register_metric_collector(OUTBOX_PROCESSING_GAUGE)
        _register_metric_collector(OUTBOX_FAILED_GAUGE)
        _register_metric_collector(OUTBOX_DLQ_GAUGE)
    except ImportError:
        pass

    try:
        from platform_api.services.scheduler_service import (
            SCHEDULER_JOB_DURATION,
            SCHEDULER_JOBS_TOTAL,
            SCHEDULER_LEADER_GAUGE,
            SCHEDULER_QUEUE_DEPTH,
        )
        _register_metric_collector(SCHEDULER_JOBS_TOTAL)
        _register_metric_collector(SCHEDULER_JOB_DURATION)
        _register_metric_collector(SCHEDULER_LEADER_GAUGE)
        _register_metric_collector(SCHEDULER_QUEUE_DEPTH)
    except ImportError:
        pass

    try:
        from platform_api.services.memory_monitor import (
            MEMORY_GROWTH_RATE,
            PROCESS_MEMORY_BYTES,
            PROCESS_MEMORY_PERCENT,
            PROCESS_MEMORY_RSS,
            PROCESS_MEMORY_VMS,
        )
        _register_metric_collector(PROCESS_MEMORY_BYTES)
        _register_metric_collector(PROCESS_MEMORY_RSS)
        _register_metric_collector(PROCESS_MEMORY_VMS)
        _register_metric_collector(PROCESS_MEMORY_PERCENT)
        _register_metric_collector(MEMORY_GROWTH_RATE)
    except ImportError:
        pass

    try:
        from platform_api.services.workflow_scheduler_service import (
            WORKFLOW_SCHEDULED_TOTAL,
            WORKFLOW_SCHEDULE_GAUGE,
            WORKFLOW_TRIGGER_TOTAL,
        )
        _register_metric_collector(WORKFLOW_SCHEDULED_TOTAL)
        _register_metric_collector(WORKFLOW_TRIGGER_TOTAL)
        _register_metric_collector(WORKFLOW_SCHEDULE_GAUGE)
    except ImportError:
        pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UUID_PATTERN = __import__("re").compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", __import__("re").IGNORECASE
)


def _normalise_path(path: str) -> str:
    """Replace UUID path segments with ``{id}`` for metric label cardinality."""
    return _UUID_PATTERN.sub("{id}", path)

