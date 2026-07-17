"""M15 TG1 — Helm chart structural validation tests.

Verifies that the platform Helm chart at ``helm/platform/`` has all required
files with correct structure, without needing the ``helm`` CLI installed.
"""
from __future__ import annotations

import yaml
from pathlib import Path

import pytest

# Root of the Helm chart relative to this test file
_CHART_ROOT = Path(__file__).parent.parent / "helm" / "platform"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_yaml(rel_path: str) -> dict:
    full = _CHART_ROOT / rel_path
    with open(full) as f:
        return yaml.safe_load(f)


def _exists(rel_path: str) -> bool:
    return (_CHART_ROOT / rel_path).exists()


# ---------------------------------------------------------------------------
# Chart.yaml
# ---------------------------------------------------------------------------


class TestChartYaml:
    def setup_method(self):
        self.chart = _load_yaml("Chart.yaml")

    def test_chart_yaml_exists(self):
        assert _exists("Chart.yaml")

    def test_chart_name(self):
        assert self.chart["name"] == "platform"

    def test_chart_type_is_application(self):
        assert self.chart["type"] == "application"

    def test_chart_version_present(self):
        assert "version" in self.chart
        parts = self.chart["version"].split(".")
        assert len(parts) == 3

    def test_chart_app_version_present(self):
        assert "appVersion" in self.chart

    def test_chart_api_version_v2(self):
        assert self.chart["apiVersion"] == "v2"

    def test_chart_description_present(self):
        assert "description" in self.chart
        assert len(self.chart["description"]) > 10


# ---------------------------------------------------------------------------
# values.yaml
# ---------------------------------------------------------------------------


class TestValuesYaml:
    def setup_method(self):
        self.values = _load_yaml("values.yaml")

    def test_values_yaml_exists(self):
        assert _exists("values.yaml")

    def test_replica_count_default(self):
        assert self.values["replicaCount"] >= 1

    def test_image_block_present(self):
        img = self.values["image"]
        assert "repository" in img
        assert "pullPolicy" in img

    def test_service_block_present(self):
        svc = self.values["service"]
        assert svc["type"] in ("ClusterIP", "NodePort", "LoadBalancer")
        assert "port" in svc

    def test_ingress_block_present(self):
        ing = self.values["ingress"]
        assert "enabled" in ing

    def test_ingress_disabled_by_default(self):
        assert self.values["ingress"]["enabled"] is False

    def test_resources_block_present(self):
        res = self.values["resources"]
        assert "requests" in res
        assert "limits" in res

    def test_liveness_probe_present(self):
        assert "livenessProbe" in self.values
        assert self.values["livenessProbe"]["httpGet"]["path"] == "/healthz"

    def test_readiness_probe_present(self):
        assert "readinessProbe" in self.values
        assert self.values["readinessProbe"]["httpGet"]["path"] == "/healthz"

    def test_config_block_has_auth_mode(self):
        assert "AUTH_MODE" in self.values["config"]

    def test_config_block_has_api_port(self):
        assert "API_PORT" in self.values["config"]
        assert self.values["config"]["API_PORT"] == "8000"

    def test_db_block_present(self):
        db = self.values["db"]
        assert "host" in db
        assert "name" in db
        assert "user" in db

    def test_db_existing_secret_default_empty(self):
        assert self.values["db"]["existingSecret"] == ""

    def test_autoscaling_disabled_by_default(self):
        assert self.values["autoscaling"]["enabled"] is False

    def test_postgres_disabled_by_default(self):
        assert self.values["postgres"]["enabled"] is False

    def test_pod_annotations_have_prometheus_scrape(self):
        annotations = self.values.get("podAnnotations", {})
        assert annotations.get("prometheus.io/scrape") == "true"
        assert annotations.get("prometheus.io/path") == "/metrics"


# ---------------------------------------------------------------------------
# Required template files
# ---------------------------------------------------------------------------


REQUIRED_TEMPLATES = [
    "templates/_helpers.tpl",
    "templates/deployment.yaml",
    "templates/service.yaml",
    "templates/configmap.yaml",
    "templates/serviceaccount.yaml",
    "templates/ingress.yaml",
    "templates/hpa.yaml",
    "templates/secret-db.yaml",
    "templates/postgres.yaml",
]


@pytest.mark.parametrize("rel_path", REQUIRED_TEMPLATES)
def test_required_template_exists(rel_path):
    assert _exists(rel_path), f"Missing required file: helm/platform/{rel_path}"


@pytest.mark.parametrize("rel_path", REQUIRED_TEMPLATES)
def test_required_template_not_empty(rel_path):
    content = (_CHART_ROOT / rel_path).read_text()
    assert len(content.strip()) > 0, f"Template is empty: {rel_path}"


# ---------------------------------------------------------------------------
# Template content checks (regex / string-based, no Helm rendering)
# ---------------------------------------------------------------------------


def _template_content(rel_path: str) -> str:
    return (_CHART_ROOT / rel_path).read_text()


def test_deployment_references_container_port_8000():
    content = _template_content("templates/deployment.yaml")
    assert "containerPort: 8000" in content


def test_deployment_uses_liveness_probe():
    content = _template_content("templates/deployment.yaml")
    assert "livenessProbe" in content


def test_deployment_uses_configmap_env():
    content = _template_content("templates/deployment.yaml")
    assert "configMapKeyRef" in content


def test_deployment_uses_secret_env():
    content = _template_content("templates/deployment.yaml")
    assert "secretKeyRef" in content


def test_service_exposes_http_port():
    content = _template_content("templates/service.yaml")
    assert "name: http" in content


def test_ingress_gated_by_enabled_flag():
    content = _template_content("templates/ingress.yaml")
    assert ".Values.ingress.enabled" in content


def test_hpa_gated_by_autoscaling_enabled():
    content = _template_content("templates/hpa.yaml")
    assert ".Values.autoscaling.enabled" in content


def test_postgres_gated_by_postgres_enabled():
    content = _template_content("templates/postgres.yaml")
    assert ".Values.postgres.enabled" in content


def test_secret_db_gated_by_existing_secret():
    content = _template_content("templates/secret-db.yaml")
    assert ".Values.db.existingSecret" in content


def test_helpers_defines_fullname():
    content = _template_content("templates/_helpers.tpl")
    assert "define \"platform.fullname\"" in content


def test_helpers_defines_labels():
    content = _template_content("templates/_helpers.tpl")
    assert "define \"platform.labels\"" in content


def test_helpers_defines_selector_labels():
    content = _template_content("templates/_helpers.tpl")
    assert "define \"platform.selectorLabels\"" in content


# ---------------------------------------------------------------------------
# README
# ---------------------------------------------------------------------------


def test_readme_exists():
    assert _exists("README.md")


def test_readme_has_quick_start_section():
    content = (_CHART_ROOT / "README.md").read_text()
    assert "Quick Start" in content


def test_readme_documents_slo_targets():
    content = (_CHART_ROOT / "README.md").read_text()
    assert "SLO" in content or "slo" in content.lower()
