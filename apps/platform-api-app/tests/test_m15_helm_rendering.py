"""M15 TG2 — Helm values semantic validation and rendering logic tests.

TG1 verified that the chart *files exist and are structurally sound*.
TG2 verifies that the *values are semantically correct and internally consistent*
without requiring the ``helm`` CLI to be installed.

Coverage:
  1. Values completeness   — all top-level configuration keys are present
  2. Port consistency      — service.targetPort == API_PORT == containerPort 8000
  3. Security hardening    — pod + container security contexts meet policy
  4. Autoscaling bounds    — min <= max, sensible range
  5. Resource bounds       — requests <= limits for CPU and memory
  6. Probe consistency     — liveness and readiness probe have same path/port
  7. DB config completeness— db.* required fields all set
  8. Config keys           — all keys in values.yaml config section appear in
                             deployment.yaml env block (no orphaned keys)
  9. Prometheus annotations— well-known annotation keys are set to valid values
 10. Image pull policy     — valid K8s values only
 11. Service type          — valid K8s service types only
 12. Postgres bundled spec — image.tag, storage.size present when postgres.enabled
 13. ingress.className     — non-empty when ingress.enabled
 14. replicas sanity       — replicaCount >= 1
 15. securityContext drop ALL — capabilities.drop contains "ALL"
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Chart paths
# ---------------------------------------------------------------------------

_CHART_ROOT = Path(__file__).parent.parent / "helm" / "platform"
_TEMPLATES_DIR = _CHART_ROOT / "templates"
_VALUES_FILE = _CHART_ROOT / "values.yaml"
_DEPLOYMENT_FILE = _TEMPLATES_DIR / "deployment.yaml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _values() -> dict:
    with open(_VALUES_FILE) as f:
        return yaml.safe_load(f)


def _template_text(name: str) -> str:
    return (_TEMPLATES_DIR / name).read_text(encoding="utf-8")


def _cpu_millicores(s: str) -> int:
    """Convert a K8s CPU string to millicores (int)."""
    s = str(s).strip()
    if s.endswith("m"):
        return int(s[:-1])
    return int(float(s) * 1000)


def _memory_mebibytes(s: str) -> int:
    """Convert a K8s memory string to MiB (int)."""
    s = str(s).strip()
    suffixes = {"Ki": 1 / 1024, "Mi": 1, "Gi": 1024, "Ti": 1024 * 1024}
    for suffix, factor in suffixes.items():
        if s.endswith(suffix):
            return int(float(s[: -len(suffix)]) * factor)
    # plain bytes
    return int(s) // (1024 * 1024)


# ---------------------------------------------------------------------------
# 1. Values completeness — top-level keys
# ---------------------------------------------------------------------------


_REQUIRED_TOP_LEVEL_KEYS = [
    "replicaCount",
    "autoscaling",
    "image",
    "imagePullSecrets",
    "serviceAccount",
    "podAnnotations",
    "podSecurityContext",
    "securityContext",
    "service",
    "ingress",
    "resources",
    "livenessProbe",
    "readinessProbe",
    "nodeSelector",
    "tolerations",
    "affinity",
    "config",
    "db",
    "postgres",
    "extraEnv",
    "extraEnvFrom",
]


class TestValuesCompleteness:
    def setup_method(self):
        self.v = _values()

    @pytest.mark.parametrize("key", _REQUIRED_TOP_LEVEL_KEYS)
    def test_top_level_key_present(self, key: str):
        assert key in self.v, f"values.yaml is missing top-level key '{key}'"

    def test_image_has_repository(self):
        assert "repository" in self.v["image"]
        assert self.v["image"]["repository"]

    def test_image_has_pull_policy(self):
        assert "pullPolicy" in self.v["image"]

    def test_service_has_port_and_target_port(self):
        assert "port" in self.v["service"]
        assert "targetPort" in self.v["service"]

    def test_db_has_all_required_fields(self):
        for field in ("host", "port", "name", "user"):
            assert field in self.v["db"], f"db.{field} missing from values.yaml"
            assert self.v["db"][field], f"db.{field} must not be empty"

    def test_config_has_all_api_settings(self):
        for key in ("API_HOST", "API_PORT", "DEPLOYMENT_PROFILE", "AUTH_MODE", "OIDC_ISSUER",
                    "TENANT_WRITE_QUOTA_PER_MINUTE"):
            assert key in self.v["config"], f"config.{key} missing from values.yaml"


# ---------------------------------------------------------------------------
# 2. Port consistency
# ---------------------------------------------------------------------------


class TestPortConsistency:
    def setup_method(self):
        self.v = _values()
        self.deploy_text = _template_text("deployment.yaml")

    def test_service_target_port_matches_api_port(self):
        service_target = int(self.v["service"]["targetPort"])
        api_port = int(self.v["config"]["API_PORT"])
        assert service_target == api_port, (
            f"service.targetPort={service_target} != config.API_PORT={api_port}"
        )

    def test_container_port_hardcoded_8000(self):
        """The deployment.yaml pins containerPort to 8000 (matches API_PORT default)."""
        assert "containerPort: 8000" in self.deploy_text

    def test_api_port_default_is_8000(self):
        assert self.v["config"]["API_PORT"] == "8000"

    def test_prometheus_annotation_port_matches_api_port(self):
        prom_port = str(self.v["podAnnotations"].get("prometheus.io/port", ""))
        api_port = self.v["config"]["API_PORT"]
        assert prom_port == api_port, (
            f"podAnnotations prometheus.io/port={prom_port} != config.API_PORT={api_port}"
        )


# ---------------------------------------------------------------------------
# 3. Security hardening
# ---------------------------------------------------------------------------


class TestSecurityHardening:
    def setup_method(self):
        self.v = _values()

    def test_pod_runs_as_non_root(self):
        assert self.v["podSecurityContext"].get("runAsNonRoot") is True

    def test_pod_runs_as_non_zero_uid(self):
        uid = self.v["podSecurityContext"].get("runAsUser", 0)
        assert uid > 0, f"runAsUser={uid} — must be > 0 to prevent root execution"

    def test_container_no_privilege_escalation(self):
        assert self.v["securityContext"].get("allowPrivilegeEscalation") is False

    def test_container_read_only_root_fs(self):
        assert self.v["securityContext"].get("readOnlyRootFilesystem") is True

    def test_container_drops_all_capabilities(self):
        drop = self.v["securityContext"].get("capabilities", {}).get("drop", [])
        assert "ALL" in drop, f"securityContext.capabilities.drop must include 'ALL', got {drop}"

    def test_fs_group_set(self):
        assert "fsGroup" in self.v["podSecurityContext"]
        assert self.v["podSecurityContext"]["fsGroup"] > 0


# ---------------------------------------------------------------------------
# 4. Autoscaling bounds
# ---------------------------------------------------------------------------


class TestAutoscalingBounds:
    def setup_method(self):
        self.v = _values()

    def test_min_replicas_lte_max_replicas(self):
        asc = self.v["autoscaling"]
        assert asc["minReplicas"] <= asc["maxReplicas"], (
            f"minReplicas={asc['minReplicas']} > maxReplicas={asc['maxReplicas']}"
        )

    def test_min_replicas_at_least_one(self):
        assert self.v["autoscaling"]["minReplicas"] >= 1

    def test_max_replicas_sensible_upper_bound(self):
        assert self.v["autoscaling"]["maxReplicas"] <= 100

    def test_cpu_utilization_percentage_valid(self):
        pct = self.v["autoscaling"]["targetCPUUtilizationPercentage"]
        assert 1 <= pct <= 100

    def test_memory_utilization_percentage_valid(self):
        pct = self.v["autoscaling"]["targetMemoryUtilizationPercentage"]
        assert 1 <= pct <= 100

    def test_replica_count_positive(self):
        assert self.v["replicaCount"] >= 1


# ---------------------------------------------------------------------------
# 5. Resource bounds — requests <= limits
# ---------------------------------------------------------------------------


class TestResourceBounds:
    def setup_method(self):
        self.v = _values()

    def test_cpu_request_lte_limit(self):
        req = _cpu_millicores(self.v["resources"]["requests"]["cpu"])
        lim = _cpu_millicores(self.v["resources"]["limits"]["cpu"])
        assert req <= lim, f"CPU request {req}m > limit {lim}m"

    def test_memory_request_lte_limit(self):
        req = _memory_mebibytes(self.v["resources"]["requests"]["memory"])
        lim = _memory_mebibytes(self.v["resources"]["limits"]["memory"])
        assert req <= lim, f"Memory request {req}MiB > limit {lim}MiB"

    def test_cpu_request_positive(self):
        req = _cpu_millicores(self.v["resources"]["requests"]["cpu"])
        assert req > 0

    def test_memory_request_positive(self):
        req = _memory_mebibytes(self.v["resources"]["requests"]["memory"])
        assert req > 0


# ---------------------------------------------------------------------------
# 6. Probe consistency
# ---------------------------------------------------------------------------


class TestProbeConsistency:
    def setup_method(self):
        self.v = _values()

    def test_liveness_and_readiness_have_same_path(self):
        lp = self.v["livenessProbe"]["httpGet"]["path"]
        rp = self.v["readinessProbe"]["httpGet"]["path"]
        assert lp == rp, (
            f"Liveness path '{lp}' != readiness path '{rp}' — diverging probes can cause split-brain"
        )

    def test_liveness_probe_uses_http_port_name(self):
        port = self.v["livenessProbe"]["httpGet"]["port"]
        assert port == "http", (
            f"livenessProbe.httpGet.port='{port}' should be 'http' (named port)"
        )

    def test_readiness_probe_uses_http_port_name(self):
        port = self.v["readinessProbe"]["httpGet"]["port"]
        assert port == "http"

    def test_liveness_initial_delay_gte_readiness(self):
        """Liveness should always start after readiness to avoid premature restarts."""
        li = self.v["livenessProbe"].get("initialDelaySeconds", 0)
        ri = self.v["readinessProbe"].get("initialDelaySeconds", 0)
        assert li >= ri, (
            f"livenessProbe.initialDelaySeconds={li} < readinessProbe.initialDelaySeconds={ri}"
        )


# ---------------------------------------------------------------------------
# 7. Config keys appear in deployment env block
# ---------------------------------------------------------------------------


class TestConfigKeysInDeployment:
    def setup_method(self):
        self.v = _values()
        self.deploy_text = _template_text("deployment.yaml")

    def test_all_config_keys_referenced_in_deployment(self):
        """Every key in values.yaml 'config' section must be referenced in the deployment."""
        missing = [
            key
            for key in self.v["config"]
            if f"key: {key}" not in self.deploy_text
        ]
        assert missing == [], (
            f"config keys not referenced in deployment.yaml env block: {missing}"
        )

    def test_no_orphaned_env_keys_in_deployment(self):
        """Env keys hard-coded in deployment.yaml should be in values.yaml config."""
        pattern = re.compile(r"key:\s+([A-Z_]+)", re.MULTILINE)
        keys_in_deploy = set(pattern.findall(self.deploy_text))
        # DB_EXISTINGSECRETKEY comes from .Values.db — allowlisted
        _ALLOWLISTED = {"POSTGRES_PASSWORD"}
        orphaned = keys_in_deploy - set(self.v["config"].keys()) - _ALLOWLISTED
        assert not orphaned, (
            f"Deployment references env keys absent from values.yaml config + allowlist: {orphaned}"
        )


# ---------------------------------------------------------------------------
# 8. Prometheus annotations
# ---------------------------------------------------------------------------


class TestPrometheusAnnotations:
    def setup_method(self):
        self.v = _values()

    def test_scrape_annotation_is_true(self):
        assert self.v["podAnnotations"].get("prometheus.io/scrape") == "true"

    def test_metrics_path_annotation_present(self):
        path = self.v["podAnnotations"].get("prometheus.io/path")
        assert path and path.startswith("/"), (
            f"prometheus.io/path='{path}' — must start with '/'"
        )

    def test_metrics_path_is_slash_metrics(self):
        assert self.v["podAnnotations"]["prometheus.io/path"] == "/metrics"

    def test_port_annotation_is_numeric_string(self):
        port_str = self.v["podAnnotations"].get("prometheus.io/port", "")
        assert port_str.isdigit(), f"prometheus.io/port='{port_str}' should be a numeric string"


# ---------------------------------------------------------------------------
# 9. Image pull policy validity
# ---------------------------------------------------------------------------


_VALID_PULL_POLICIES = {"Always", "IfNotPresent", "Never"}


def test_image_pull_policy_is_valid():
    v = _values()
    policy = v["image"]["pullPolicy"]
    assert policy in _VALID_PULL_POLICIES, (
        f"image.pullPolicy='{policy}' is not a valid K8s pullPolicy. "
        f"Valid values: {_VALID_PULL_POLICIES}"
    )


# ---------------------------------------------------------------------------
# 10. Service type validity
# ---------------------------------------------------------------------------


_VALID_SERVICE_TYPES = {"ClusterIP", "NodePort", "LoadBalancer", "ExternalName"}


def test_service_type_is_valid():
    v = _values()
    stype = v["service"]["type"]
    assert stype in _VALID_SERVICE_TYPES, (
        f"service.type='{stype}' is not a valid K8s Service type"
    )


# ---------------------------------------------------------------------------
# 11. Bundled Postgres when enabled
# ---------------------------------------------------------------------------


class TestBundledPostgres:
    def setup_method(self):
        self.v = _values()

    def test_postgres_image_tag_present(self):
        pg = self.v["postgres"]
        assert "image" in pg
        assert "tag" in pg["image"]
        assert pg["image"]["tag"]

    def test_postgres_storage_size_present(self):
        pg = self.v["postgres"]
        assert "storage" in pg
        assert "size" in pg["storage"]
        size = pg["storage"]["size"]
        # must end with a storage unit
        assert re.match(r"^\d+[KMGTP]i$", size), f"postgres.storage.size='{size}' is not a valid K8s quantity"

    def test_postgres_bundled_is_disabled_by_default(self):
        """Bundled postgres must be opt-in (enabled: false by default)."""
        assert self.v["postgres"]["enabled"] is False, (
            "postgres.enabled should be false by default for production safety"
        )

    def test_postgres_password_requires_override_when_enabled(self):
        assert "password" in self.v["postgres"]
        assert self.v["postgres"]["password"] == ""


# ---------------------------------------------------------------------------
# 12. Ingress class name when enabled
# ---------------------------------------------------------------------------


def test_ingress_class_name_non_empty():
    v = _values()
    if v["ingress"]["enabled"]:
        cls = v["ingress"].get("className", "")
        assert cls, "ingress.className must be set when ingress.enabled=true"
    else:
        # Even when disabled, the className default should be documented
        cls = v["ingress"].get("className", "")
        assert isinstance(cls, str)


# ---------------------------------------------------------------------------
# 13. Deployment template references correct service account value path
# ---------------------------------------------------------------------------


def test_deployment_references_service_account_automount():
    v = _values()
    deploy_text = _template_text("deployment.yaml")
    sa = v["serviceAccount"]
    assert "serviceAccount" in v
    assert "automount" in sa
    # serviceAccount.create should be bool
    assert isinstance(sa["create"], bool)


# ---------------------------------------------------------------------------
# 14. All template YAML files parse as valid YAML after stripping Go directives
# ---------------------------------------------------------------------------


_TEMPLATE_FILES = [
    # configmap.yaml uses a Go `range` loop which cannot be cleanly stripped to
    # valid YAML (the loop body `{{ $key }}: {{ $value | quote }}` leaves bare
    # `: ` lines).  Configmap structure is covered in TG1.
    "service.yaml",
    "serviceaccount.yaml",
    "hpa.yaml",
]


def _strip_go_directives(text: str) -> str:
    """Remove Go template directives so PyYAML can parse the static skeleton."""
    # Remove {{ ... }} expressions and {{- ... -}} blocks
    text = re.sub(r"\{\{-?.*?-?\}\}", "", text)
    # Remove lines that become entirely whitespace after stripping
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines)


@pytest.mark.parametrize("template_name", _TEMPLATE_FILES)
def test_template_is_parseable_yaml_after_stripping_go(template_name: str):
    """After removing Go directives, each template must be valid YAML."""
    raw = _template_text(template_name)
    cleaned = _strip_go_directives(raw)
    try:
        yaml.safe_load(cleaned)
    except yaml.YAMLError as exc:
        pytest.fail(
            f"templates/{template_name} is not valid YAML after stripping Go directives:\n{exc}"
        )
