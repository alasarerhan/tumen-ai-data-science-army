"""
Tests for ``ai_data_science_team.tools.model_serving`` (G3 tool layer).
"""

from __future__ import annotations


from ai_data_science_team.tools.model_serving import (
    PORT_POOL,
    allocate_port,
    record_deployment,
    record_rollback,
    render_bentofile,
    render_dockerfile,
    render_fastapi_app,
)


class TestAllocatePort:
    def test_first_port_default(self):
        assert allocate_port() == PORT_POOL[0]

    def test_skips_used_ports(self):
        used = {8100, 8101}
        port = allocate_port(used)
        assert port == 8102

    def test_pool_handling(self):
        # Fill the pool except for one port.
        used = set(PORT_POOL) - {PORT_POOL[-1]}
        assert allocate_port(used) == PORT_POOL[-1]


class TestRenderDockerfile:
    def test_basic(self):
        df = render_dockerfile("churn_xgb", "3")
        assert "churn_xgb" in df
        assert "MODEL_VERSION=3" in df
        assert "EXPOSE 8000" in df

    def test_custom_python_version(self):
        df = render_dockerfile("m", "1", python_version="3.10")
        assert "python:3.10-slim" in df


class TestRenderBentofile:
    def test_basic(self):
        bf = render_bentofile("m", "2")
        assert "model_id: \"m\"" in bf
        assert "model_version: \"2\"" in bf
        assert "bentoml serve" in bf


class TestRenderFastApiApp:
    def test_route_default(self):
        app = render_fastapi_app("m", "1")
        assert "/predict" in app
        assert "FastAPI" in app
        assert "/healthz" in app

    def test_custom_route(self):
        app = render_fastapi_app("m", "1", route="/score")
        assert "/score" in app


class TestDeploymentAndRollback:
    def test_record_deployment_minimal(self):
        rec = record_deployment(
            model_id="m", version="1", target="endpoint"
        )
        assert rec["model_id"] == "m"
        assert rec["version"] == "1"
        assert rec["target"] == "endpoint"
        assert rec["status"] == "pending"
        assert rec["port"] is None
        assert len(rec["deployment_id"]) > 10

    def test_record_deployment_full(self):
        rec = record_deployment(
            model_id="m", version="2", target="container",
            port=8103, status="running", artifacts={"image": "m:v2"}
        )
        assert rec["port"] == 8103
        assert rec["artifacts"] == {"image": "m:v2"}

    def test_record_rollback(self):
        out = record_rollback(
            deployment_id="d1", from_version="3", to_version="2",
            reason="drift detected"
        )
        assert out["from_version"] == "3"
        assert out["to_version"] == "2"
        assert "drift" in out["reason"]
