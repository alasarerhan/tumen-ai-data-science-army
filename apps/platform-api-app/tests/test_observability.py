"""Tests for M7 — observability hardening.

Each test creates an *isolated* CollectorRegistry so Prometheus global state
does not bleed between tests.
"""
from __future__ import annotations

import json
import logging
import time
import uuid

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from platform_api.core.observability import (
    SLO_AVAILABILITY_BUDGET,
    SLO_ERROR_RATE_BUDGET,
    SLO_LATENCY_P99_MS,
    _JsonFormatter,
    _REGISTRY,
    _normalise_path,
    configure_logging,
    setup_observability,
)


# ---------------------------------------------------------------------------
# SLO constant sanity checks
# ---------------------------------------------------------------------------


def test_slo_latency_constant():
    assert SLO_LATENCY_P99_MS == 500


def test_slo_error_budget_constant():
    assert SLO_ERROR_RATE_BUDGET == pytest.approx(0.01)


def test_slo_availability_budget_constant():
    assert SLO_AVAILABILITY_BUDGET == pytest.approx(0.995)


# ---------------------------------------------------------------------------
# Path normalisation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("/api/workspaces/3fa85f64-5717-4562-b3fc-2c963f66afa6/workflows", "/api/workspaces/{id}/workflows"),
        ("/health", "/health"),
        ("/api/tenants/00000000-0000-0000-0000-000000000000", "/api/tenants/{id}"),
        ("/no-uuid-here", "/no-uuid-here"),
    ],
)
def test_normalise_path(raw: str, expected: str):
    assert _normalise_path(raw) == expected


# ---------------------------------------------------------------------------
# JSON formatter
# ---------------------------------------------------------------------------


def _make_record(msg: str, level: int = logging.INFO) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test", level=level, pathname="", lineno=0,
        msg=msg, args=(), exc_info=None,
    )
    return record


def test_json_formatter_plain_message():
    fmt = _JsonFormatter()
    out = json.loads(fmt.format(_make_record("hello")))
    assert out["message"] == "hello"
    assert out["severity"] == "INFO"
    assert out["service"] == "platform-api"


def test_json_formatter_warning_severity():
    fmt = _JsonFormatter()
    out = json.loads(fmt.format(_make_record("warn!", logging.WARNING)))
    assert out["severity"] == "WARNING"


def test_json_formatter_merges_json_payload():
    fmt = _JsonFormatter()
    payload = json.dumps({"event": "http_request", "status_code": 200})
    out = json.loads(fmt.format(_make_record(payload)))
    assert out["event"] == "http_request"
    assert out["status_code"] == 200


def test_configure_logging_sets_json_handler():
    configure_logging()
    root = logging.getLogger()
    assert any(isinstance(h.formatter, _JsonFormatter) for h in root.handlers)


# ---------------------------------------------------------------------------
# FastAPI integration — isolated registry per test
# ---------------------------------------------------------------------------


def _build_app_with_isolated_registry() -> tuple[FastAPI, CollectorRegistry]:
    """Return a fresh FastAPI app + isolated prometheus registry."""
    reg = CollectorRegistry(auto_describe=True)

    requests_total = Counter(
        "test_http_requests_total", "Test counter", ["method", "path", "status"], registry=reg
    )
    duration = Histogram(
        "test_http_request_duration_seconds", "Test histogram", ["method", "path"], registry=reg
    )
    in_flight = Gauge("test_in_flight", "Test gauge", registry=reg)

    app = FastAPI()

    @app.get("/ping")
    async def ping():
        return {"pong": True}

    @app.get("/error")
    async def boom():
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="boom")

    # Minimal middleware that uses the isolated counters
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request

    class _TestMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            in_flight.inc()
            start = time.perf_counter()
            response = await call_next(request)
            elapsed = time.perf_counter() - start
            in_flight.dec()
            path = _normalise_path(request.url.path)
            requests_total.labels(
                method=request.method, path=path, status=str(response.status_code)
            ).inc()
            duration.labels(method=request.method, path=path).observe(elapsed)
            return response

    app.add_middleware(_TestMiddleware)

    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        from fastapi import Response
        return Response(content=generate_latest(reg), media_type=CONTENT_TYPE_LATEST)

    return app, reg


def test_metrics_endpoint_returns_200():
    app, _ = _build_app_with_isolated_registry()
    client = TestClient(app)
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]


def test_request_increments_counter():
    app, reg = _build_app_with_isolated_registry()
    client = TestClient(app)
    client.get("/ping")
    metrics_text = generate_latest(reg).decode()
    assert 'test_http_requests_total{method="GET",path="/ping",status="200"}' in metrics_text


def test_error_request_tracked():
    app, reg = _build_app_with_isolated_registry()
    client = TestClient(app, raise_server_exceptions=False)
    client.get("/error")
    metrics_text = generate_latest(reg).decode()
    assert 'status="500"' in metrics_text


def test_histogram_populated():
    app, reg = _build_app_with_isolated_registry()
    client = TestClient(app)
    client.get("/ping")
    client.get("/ping")
    metrics_text = generate_latest(reg).decode()
    assert "test_http_request_duration_seconds_count" in metrics_text


def test_module_registry_has_expected_metrics():
    """The module-level _REGISTRY has the three platform_api metrics."""
    metrics_text = generate_latest(_REGISTRY).decode()
    assert "platform_api_http_requests_total" in metrics_text
    assert "platform_api_http_request_duration_seconds" in metrics_text
    assert "platform_api_http_requests_in_flight" in metrics_text
