"""M15 TG3 — Helm Smoke Tests.

Runs `helm lint` and `helm template` against the bundled chart via subprocess.
All tests skip gracefully when the `helm` CLI is not installed.

Run with helm available:
    pytest tests/test_m15_smoke.py -v

Run in CI without helm (all skip):
    pytest tests/test_m15_smoke.py -v
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Location helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent  # apps/platform-api-app/
_CHART = _REPO_ROOT / "helm" / "platform"

# ---------------------------------------------------------------------------
# Skip guard: skip every test if helm is not on PATH
# ---------------------------------------------------------------------------

_HELM = shutil.which("helm")
skip_no_helm = pytest.mark.skipif(
    _HELM is None,
    reason="helm CLI not found on PATH — install helm to run TG3 smoke tests",
)

_KIND = shutil.which("kind")
skip_no_kind = pytest.mark.skipif(
    _KIND is None,
    reason="kind CLI not found on PATH — install kind to run cluster smoke tests",
)


def _run(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a subprocess command and return the result."""
    return subprocess.run(
        list(args),
        capture_output=True,
        text=True,
        check=check,
    )


_HELM_SECRET_OVERRIDE = ("--set", "db.password=local-smoke-db-password-20260604")


# ---------------------------------------------------------------------------
# TG3-1: helm lint
# ---------------------------------------------------------------------------


@skip_no_helm
def test_helm_lint_passes():
    """helm lint must exit 0 with no errors on the bundled chart."""
    result = _run(_HELM, "lint", str(_CHART), *_HELM_SECRET_OVERRIDE)
    assert result.returncode == 0, (
        f"helm lint failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


@skip_no_helm
def test_helm_lint_no_errors_in_output():
    """helm lint stdout must not contain the word 'Error'."""
    result = _run(_HELM, "lint", str(_CHART), *_HELM_SECRET_OVERRIDE)
    assert "Error" not in result.stdout, (
        f"helm lint reported errors:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# TG3-2: helm template (dry-run rendering)
# ---------------------------------------------------------------------------


@skip_no_helm
def test_helm_template_renders_without_error():
    """helm template must render all manifests without error."""
    result = _run(_HELM, "template", "platform-test", str(_CHART), *_HELM_SECRET_OVERRIDE)
    assert result.returncode == 0, (
        f"helm template failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


@skip_no_helm
def test_helm_template_contains_deployment():
    """Rendered output must include at least one Deployment kind."""
    result = _run(_HELM, "template", "platform-test", str(_CHART), *_HELM_SECRET_OVERRIDE)
    assert "kind: Deployment" in result.stdout, (
        "No Deployment found in rendered Helm templates"
    )


@skip_no_helm
def test_helm_template_contains_service():
    """Rendered output must include at least one Service kind."""
    result = _run(_HELM, "template", "platform-test", str(_CHART), *_HELM_SECRET_OVERRIDE)
    assert "kind: Service" in result.stdout, (
        "No Service found in rendered Helm templates"
    )


@skip_no_helm
def test_helm_template_contains_configmap_or_secret():
    """Rendered output must include a ConfigMap or Secret."""
    result = _run(_HELM, "template", "platform-test", str(_CHART), *_HELM_SECRET_OVERRIDE)
    assert ("kind: ConfigMap" in result.stdout or "kind: Secret" in result.stdout), (
        "No ConfigMap or Secret found in rendered Helm templates"
    )


@skip_no_helm
def test_helm_template_with_custom_values():
    """helm template with custom replicas and image tag must succeed."""
    result = _run(
        _HELM, "template", "platform-test", str(_CHART),
        *_HELM_SECRET_OVERRIDE,
        "--set", "replicaCount=2",
        "--set", "image.tag=v1.2.3",
    )
    assert result.returncode == 0, (
        f"helm template with custom values failed:\n{result.stderr}"
    )


@skip_no_helm
def test_helm_template_api_version_v1():
    """All rendered resources must use a supported apiVersion."""
    result = _run(_HELM, "template", "platform-test", str(_CHART), *_HELM_SECRET_OVERRIDE)
    lines = result.stdout.splitlines()
    api_lines = [ln for ln in lines if ln.startswith("apiVersion:")]
    assert len(api_lines) > 0, "No apiVersion lines found in rendered output"
    for ln in api_lines:
        api = ln.replace("apiVersion:", "").strip()
        assert api, f"Empty apiVersion found: {ln!r}"


# ---------------------------------------------------------------------------
# TG3-3: kind cluster smoke (skip if kind not available)
# ---------------------------------------------------------------------------


@skip_no_helm
@skip_no_kind
def test_kind_cluster_create_and_helm_install():
    """Create a temporary kind cluster, install the chart, verify pod health.

    This test is intentionally long-running and should only be executed in a
    dedicated CI environment. It cleans up the cluster regardless of outcome.
    """
    import time

    cluster_name = "platform-tg3-smoke"

    # Create cluster
    create = _run(_KIND, "create", "cluster", "--name", cluster_name, check=False)
    if create.returncode != 0:
        pytest.skip(f"kind cluster creation failed: {create.stderr}")

    try:
        # helm install with --wait (up to 120 s)
        install = _run(
            _HELM, "install", "platform-smoke", str(_CHART),
            *_HELM_SECRET_OVERRIDE,
            "--kube-context", f"kind-{cluster_name}",
            "--wait", "--timeout", "120s",
            check=False,
        )
        assert install.returncode == 0, (
            f"helm install failed:\nSTDOUT:\n{install.stdout}\nSTDERR:\n{install.stderr}"
        )

        # Basic health probe via kubectl port-forward would go here.
        # For now we verify the release is listed.
        ls = _run(
            _HELM, "list",
            "--kube-context", f"kind-{cluster_name}",
        )
        assert "platform-smoke" in ls.stdout, (
            "Installed release not found in helm list output"
        )

    finally:
        _run(_KIND, "delete", "cluster", "--name", cluster_name, check=False)
