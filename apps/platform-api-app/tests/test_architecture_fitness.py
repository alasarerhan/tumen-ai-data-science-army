"""
Architectural Fitness Functions

These tests validate that the codebase adheres to architectural rules and constraints.
They serve as automated governance to prevent architectural drift.

Run with: pytest tests/test_architecture_fitness.py -v
"""
from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest
from fastapi import FastAPI


ROOT_DIR = Path(__file__).parent.parent
PLATFORM_API_DIR = ROOT_DIR / "platform_api"
ROUTES_DIR = PLATFORM_API_DIR / "routes"
SERVICES_DIR = PLATFORM_API_DIR / "services"


def _read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_source(path: Path) -> ast.AST:
    return ast.parse(_read_source(path), filename=str(path))


def _iter_imports(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            yield node


def _has_apirouter_call(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "APIRouter":
                return True
            if isinstance(func, ast.Attribute) and func.attr == "APIRouter":
                return True
    return False


class TestRouteLayerIsolation:
    """Routes should not contain business logic - only request/response handling."""

    def test_routes_no_direct_db_queries(self):
        """Routes should use services, not direct SQLAlchemy queries."""
        forbidden_patterns = [
            "session.query",
            "session.execute",
            ".filter(",
            ".all()",
            ".first()",
        ]

        for route_file in ROUTES_DIR.glob("*.py"):
            if route_file.name == "__init__.py":
                continue
            content = _read_source(route_file)
            for pattern in forbidden_patterns:
                assert pattern not in content or "session: Session" in content[:500], (
                    f"Route {route_file.name} contains direct DB query pattern '{pattern}'. "
                    "Use service layer instead."
                )

    def test_routes_import_services_not_models(self):
        """Routes should import from services, not directly from db.models."""
        for route_file in ROUTES_DIR.glob("*.py"):
            if route_file.name == "__init__.py":
                continue
            content = _read_source(route_file)
            if "from platform_api.db.models import" in content:
                assert "from platform_api.services" in content, (
                    f"Route {route_file.name} imports models directly. "
                    "Import through service layer."
                )


class TestServiceLayerPurity:
    """Services should not import FastAPI dependencies."""

    def test_services_no_fastapi_imports(self):
        """Services should be framework-agnostic."""
        forbidden_modules = ("fastapi", "starlette")
        forbidden_names = {"APIRouter", "HTTPException", "Request", "Response"}

        for service_file in SERVICES_DIR.glob("*.py"):
            if service_file.name == "__init__.py":
                continue
            tree = _parse_source(service_file)
            for node in _iter_imports(tree):
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    assert not module.startswith(forbidden_modules), (
                        f"Service {service_file.name} imports FastAPI module '{module}'. "
                        "Services should be framework-agnostic."
                    )
                    bad_names = forbidden_names.intersection(alias.name for alias in node.names)
                    assert not bad_names, (
                        f"Service {service_file.name} imports FastAPI dependency names {sorted(bad_names)}. "
                        "Services should be framework-agnostic."
                    )
                elif isinstance(node, ast.Import):
                    bad_modules = [
                        alias.name for alias in node.names if alias.name.startswith(forbidden_modules)
                    ]
                    assert not bad_modules, (
                        f"Service {service_file.name} imports FastAPI modules {bad_modules}. "
                        "Services should be framework-agnostic."
                    )


class TestTenantIsolation:
    """All data access must be tenant-scoped."""

    def test_all_models_have_tenant_id(self):
        """All tenant-scoped models must have tenant_id foreign key."""
        models_file = PLATFORM_API_DIR / "db" / "models.py"
        content = _read_source(models_file)

        tenant_scoped_models = [
            "Workspace",
            "WorkflowRun",
            "Artifact",
            "WorkflowSpec",
            "DataSource",
            "HitlApproval",
            "ChatSession",
            "ChatUpload",
            "WorkflowSignalEvent",
        ]

        for model in tenant_scoped_models:
            assert f'class {model}(Base)' in content, f"Model {model} not found"
            model_class_start = content.find(f'class {model}(Base)')
            model_class_end = content.find('\nclass ', model_class_start + 1)
            if model_class_end == -1:
                model_class_end = len(content)
            model_content = content[model_class_start:model_class_end]
            assert 'tenant_id' in model_content, (
                f"Model {model} missing tenant_id. All tenant-scoped models must have tenant isolation."
            )


class TestDependencyVersionGovernance:
    """Validate dependency versions are pinned and documented."""

    def test_requirements_versions_pinned(self):
        """All requirements must have pinned versions."""
        requirements_file = ROOT_DIR / "requirements.txt"
        if not requirements_file.exists():
            pytest.skip("requirements.txt not found")

        content = requirements_file.read_text()
        for line in content.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            assert ">=" in line or "==" in line, (
                f"Dependency '{line}' should have pinned version (use >= or ==)."
            )


class TestADRCompliance:
    """Validate ADR decisions are followed in code."""

    def test_health_endpoint_is_healthz(self):
        """ADR-0002: Canonical health endpoint is /healthz."""
        health_route = ROUTES_DIR / "health.py"
        content = _read_source(health_route)
        assert '"/healthz"' in content, "ADR-0002: /healthz should be canonical endpoint"

    def test_auth_mode_oidc_default(self):
        """ADR-0003: AUTH_MODE defaults to oidc."""
        config_file = PLATFORM_API_DIR / "core" / "config.py"
        content = _read_source(config_file)
        assert "oidc" in content.lower(), "ADR-0003: AUTH_MODE should default to oidc"

    def test_single_orchestration_path(self):
        """ADR-0001: POST /v1/runs is the single orchestration entrypoint."""
        runs_route = ROUTES_DIR / "runs.py"
        content = _read_source(runs_route)
        assert 'POST' in content or 'post' in content, "ADR-0001: runs.py should have POST endpoint"
        assert '"/v1/runs"' in content or 'prefix="/v1/runs"' in content, (
            "ADR-0001: /v1/runs should be orchestration entrypoint"
        )


class TestNoCircularDependencies:
    """Prevent circular imports between modules."""

    def test_no_circular_imports_in_platform_api(self):
        """Check for obvious circular import patterns."""
        forbidden_patterns = [
            "from platform_api.routes import",
            "from platform_api.services import *",
        ]

        for py_file in PLATFORM_API_DIR.rglob("*.py"):
            content = _read_source(py_file)
            for pattern in forbidden_patterns:
                assert pattern not in content, (
                    f"Potential circular import in {py_file}: '{pattern}'"
                )


class TestCodeOrganization:
    """Validate code organization follows layered architecture."""

    def test_routes_only_in_routes_dir(self):
        """APIRouter definitions should only exist in routes/ directory."""
        for py_file in PLATFORM_API_DIR.rglob("*.py"):
            rel_path = py_file.relative_to(PLATFORM_API_DIR)
            if "routes" not in str(rel_path) and "test" not in str(rel_path):
                tree = _parse_source(py_file)
                if _has_apirouter_call(tree):
                    pytest.fail(
                        f"APIRouter found in {py_file}. "
                        "Routes should only be defined in routes/ directory."
                    )

    def test_no_business_logic_in_main(self):
        """main.py should remain a composition root, not a service layer."""
        main_file = PLATFORM_API_DIR / "main.py"
        tree = _parse_source(main_file)
        imported_modules = []
        for node in _iter_imports(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.append(node.module)
            elif isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)

        forbidden_prefixes = ("platform_api.services", "platform_api.db")
        bad_imports = [module for module in imported_modules if module.startswith(forbidden_prefixes)]
        assert not bad_imports, (
            f"main.py imports business-layer modules directly: {bad_imports}. "
            "Keep business logic in routes/services."
        )
        assert not _has_apirouter_call(tree), "main.py should not define routers."

    def test_main_import_is_side_effect_free(self):
        """Importing platform_api.main should expose the factory without building the ASGI app."""
        main_module = importlib.import_module("platform_api.main")
        assert callable(main_module.create_app)
        assert "app" not in vars(main_module), (
            "platform_api.main should expose create_app() only; runtime app belongs in platform_api.asgi."
        )


class TestObservabilityRequirements:
    """Validate observability is properly implemented."""

    def test_structured_logging_configured(self):
        """Logging should be structured (JSON) for production."""
        observability_file = PLATFORM_API_DIR / "core" / "observability.py"
        if observability_file.exists():
            content = _read_source(observability_file)
            assert "json" in content.lower() or "structlog" in content.lower(), (
                "Logging should use structured format (JSON) for production"
            )

    def test_observability_setup_is_idempotent(self):
        """Repeated setup should not duplicate middleware or /metrics routes."""
        from platform_api.core.observability import setup_observability

        app = FastAPI()
        setup_observability(app)
        setup_observability(app)

        metrics_routes = [route for route in app.routes if getattr(route, "path", None) == "/metrics"]
        assert len(metrics_routes) == 1, "setup_observability() should only register /metrics once"

    def test_create_app_does_not_start_scheduler(self, monkeypatch):
        """App construction should not start the scheduler before lifespan enters."""
        import platform_api.services.scheduler_service as scheduler_service
        from platform_api.main import create_app

        calls: list[tuple] = []

        def fail_if_called(*args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("Scheduler should not start during create_app()")

        monkeypatch.setattr(scheduler_service, "create_default_scheduler", fail_if_called)
        create_app()
        assert calls == []


class TestSecurityRequirements:
    """Validate security requirements are met."""

    def test_no_hardcoded_secrets(self):
        """No hardcoded secrets in source files."""
        secret_patterns = [
            "password = \"",
            "secret_key = \"",
            "api_key = \"",
            "token = \"",
        ]

        for py_file in PLATFORM_API_DIR.rglob("*.py"):
            if "test" in str(py_file):
                continue
            content = _read_source(py_file)
            for pattern in secret_patterns:
                assert pattern not in content.lower(), (
                    f"Potential hardcoded secret in {py_file}: '{pattern}'"
                )

    def test_sql_injection_prevention(self):
        """SQL queries should use parameterized statements."""
        for py_file in PLATFORM_API_DIR.rglob("*.py"):
            content = _read_source(py_file)
            dangerous_patterns = [
                'f"SELECT',
                'f"INSERT',
                'f"UPDATE',
                'f"DELETE',
                "+ 'SELECT",
                '+ "SELECT',
            ]
            for pattern in dangerous_patterns:
                assert pattern not in content, (
                    f"Potential SQL injection in {py_file}: '{pattern}'. Use parameterized queries."
                )


class TestPerformanceBudgets:
    """Validate performance-related architectural constraints."""

    def test_no_n_plus_one_in_models(self):
        """Models should not create N+1 query patterns."""
        models_file = PLATFORM_API_DIR / "db" / "models.py"
        content = _read_source(models_file)
        assert "lazy='select'" not in content or "lazy='joined'" in content, (
            "Consider using lazy='joined' or lazy='selectin' to prevent N+1 queries"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
