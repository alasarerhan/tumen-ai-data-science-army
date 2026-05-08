"""Contract tests using Schemathesis for API schema validation.

Validates that the API implementation matches its OpenAPI specification.
Catches breaking changes and ensures backward compatibility.

Usage
-----
Run contract tests against a running API server:

    st run --base-url http://localhost:8000 openapi.json

Or run as pytest:

    pytest tests/test_contract.py

Best Practices Reference:
https://schemathesis.readthedocs.io/
"""
from __future__ import annotations

import os
import pytest

try:
    import schemathesis
    from schemathesis import DataGenerationMethod
    SCHEMATHESIS_AVAILABLE = True
except ImportError:
    SCHEMATHESIS_AVAILABLE = False
    pytest.skip("schemathesis not installed", allow_module_level=True)

BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

if SCHEMATHESIS_AVAILABLE:
    schema = schemathesis.from_uri(
        f"{BASE_URL}/openapi.json",
        data_generation_methods=[
            DataGenerationMethod.positive,
            DataGenerationMethod.negative,
        ],
    )

    @schema.parametrize()
    def test_api_contract_positive(case):
        """Validate API responses against OpenAPI schema."""
        response = case.call(base_url=BASE_URL)
        case.validate_response(
            response,
            checks=(
                schemathesis.checks.status_code,
                schemathesis.checks.response_schema,
                schemathesis.checks.content_type,
            ),
        )

    @schema.parametrize(method=["GET"])
    def test_get_endpoints_contract(case):
        """Specifically test GET endpoints for response schema compliance."""
        response = case.call(base_url=BASE_URL)
        case.validate_response(response)

    @pytest.mark.parametrize("endpoint", [
        "/healthz",
        "/health",
        "/metrics",
    ])
    def test_health_endpoints_schema(endpoint):
        """Test health and metrics endpoints return valid responses."""
        import httpx
        response = httpx.get(f"{BASE_URL}{endpoint}")
        assert response.status_code == 200

    def test_openapi_schema_is_valid():
        """Verify OpenAPI schema can be fetched and parsed."""
        import httpx
        response = httpx.get(f"{BASE_URL}/openapi.json")
        assert response.status_code == 200
        schema_data = response.json()
        assert "openapi" in schema_data
        assert "paths" in schema_data
        assert len(schema_data["paths"]) > 0

    def test_openapi_has_required_endpoints():
        """Verify all expected endpoints are documented."""
        import httpx
        response = httpx.get(f"{BASE_URL}/openapi.json")
        schema_data = response.json()
        paths = schema_data.get("paths", {})

        required_prefixes = [
            "/v1/runs",
            "/v1/workflows",
            "/v1/artifacts",
            "/v1/chat",
            "/healthz",
        ]

        for prefix in required_prefixes:
            matching = [p for p in paths if p.startswith(prefix)]
            assert len(matching) > 0, f"No endpoints found for {prefix}"
