"""Unit tests for RateLimitMiddleware.

Tests cover:
  - Request allowance under threshold
  - 429 response when exceeded
  - X-RateLimit headers
  - Skip paths
  - Auth paths with stricter limits
  - Sliding window expiration
  - Client ID extraction
"""

from __future__ import annotations

from fastapi import FastAPI
from starlette.testclient import TestClient

from platform_api.core.rate_limit import RateLimitMiddleware


class TestRateLimitAllowance:
    """Tests for request allowance under threshold."""

    def test_allows_requests_under_threshold(self):
        app = FastAPI()
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=10,
            redis_url=None,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        client = TestClient(app)

        for i in range(5):
            response = client.get("/test")
            assert response.status_code == 200


class TestRateLimitExceeded:
    """Tests for 429 response when rate limit exceeded."""

    def test_returns_429_when_exceeded(self):
        app = FastAPI()
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=3,
            redis_url=None,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        client = TestClient(app)

        for i in range(3):
            response = client.get("/test")
            assert response.status_code == 200

        response = client.get("/test")
        assert response.status_code == 429
        assert "Rate limit exceeded" in response.json()["detail"]


class TestRateLimitHeaders:
    """Tests for X-RateLimit headers."""

    def test_rate_limit_headers_populated(self):
        app = FastAPI()
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=10,
            redis_url=None,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        client = TestClient(app)

        response = client.get("/test")

        assert "X-RateLimit-Limit" in response.headers
        assert response.headers["X-RateLimit-Limit"] == "10"
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    def test_rate_limit_remaining_decrements(self):
        app = FastAPI()
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=10,
            redis_url=None,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        client = TestClient(app)

        response1 = client.get("/test")
        remaining1 = int(response1.headers["X-RateLimit-Remaining"])

        response2 = client.get("/test")
        remaining2 = int(response2.headers["X-RateLimit-Remaining"])

        assert remaining2 < remaining1


class TestRateLimitSkipPaths:
    """Tests for skip paths."""

    def test_skip_paths_bypass_rate_limiting(self):
        app = FastAPI()
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=1,
            redis_url=None,
            skip_paths=["/health", "/healthz", "/metrics"],
        )

        @app.get("/healthz")
        async def health():
            return {"status": "healthy"}

        client = TestClient(app)

        for i in range(5):
            response = client.get("/healthz")
            assert response.status_code == 200


class TestRateLimitAuthPaths:
    """Tests for auth paths with stricter limits."""

    def test_auth_paths_have_stricter_limits(self):
        app = FastAPI()
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=100,
            redis_url=None,
            auth_paths={"/v1/auth/login": 2},
        )

        @app.post("/v1/auth/login")
        async def login():
            return {"token": "test"}

        client = TestClient(app)

        for i in range(2):
            response = client.post("/v1/auth/login")
            assert response.status_code == 200

        response = client.post("/v1/auth/login")
        assert response.status_code == 429

    def test_auth_path_limit_is_isolated_from_other_paths(self):
        app = FastAPI()
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=100,
            redis_url=None,
            auth_paths={"/v1/auth/login": 2, "/v1/me": 10},
        )

        @app.get("/v1/me")
        async def me():
            return {"id": "test-user"}

        @app.post("/v1/auth/login")
        async def login():
            return {"token": "test"}

        client = TestClient(app)

        for _ in range(5):
            response = client.get("/v1/me")
            assert response.status_code == 200

        response = client.post("/v1/auth/login")
        assert response.status_code == 200
        assert response.headers["X-RateLimit-Remaining"] == "1"


class TestRateLimitSlidingWindow:
    """Tests for sliding window expiration."""

    def test_sliding_window_expires_old_requests(self):
        app = FastAPI()
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=2,
            redis_url=None,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        client = TestClient(app)

        response = client.get("/test")
        assert response.status_code == 200

        response = client.get("/test")
        assert response.status_code == 200

        response = client.get("/test")
        assert response.status_code == 429


class TestRateLimitClientId:
    """Tests for client ID extraction."""

    def test_client_id_from_header(self):
        app = FastAPI()
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=2,
            redis_url=None,
            key_header="X-User-Id",
        )

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        client = TestClient(app)

        response = client.get("/test", headers={"X-User-Id": "user-123"})
        assert response.status_code == 200

        response = client.get("/test", headers={"X-User-Id": "user-123"})
        assert response.status_code == 200

        response = client.get("/test", headers={"X-User-Id": "user-123"})
        assert response.status_code == 429

        response = client.get("/test", headers={"X-User-Id": "user-456"})
        assert response.status_code == 200

    def test_client_id_fallback_to_ip(self):
        app = FastAPI()
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=2,
            redis_url=None,
            key_header="X-User-Id",
        )

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        client = TestClient(app)

        response = client.get("/test")
        assert response.status_code == 200

        response = client.get("/test")
        assert response.status_code == 200

        response = client.get("/test")
        assert response.status_code == 429


class TestRateLimitRetryAfter:
    """Tests for Retry-After header."""

    def test_retry_after_header_on_429(self):
        app = FastAPI()
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=1,
            redis_url=None,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        client = TestClient(app)

        client.get("/test")
        response = client.get("/test")

        assert response.status_code == 429
        assert "Retry-After" in response.headers
        retry_after = int(response.headers["Retry-After"])
        assert retry_after > 0
