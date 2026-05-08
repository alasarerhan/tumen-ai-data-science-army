"""M7 TG4 — Non-functional tests: security scan + dependency audit + performance.

Three test groups:
  1. Security (bandit)   — zero HIGH/CRITICAL severity findings in platform_api/
  2. Dependency audit    — pip-audit JSON; no unacknowledged CRITICAL CVEs
  3. Performance         — /healthz and /v1/workflows p99 latency < SLO_LATENCY_P99_MS (500 ms)

Bandit findings are intentionally not silenced with noqa comments in source;
instead the low/medium findings are explicitly acknowledged here so the test
suite stays green while the audit trail is preserved.

Dependency CVE allow-list:
  CVE-2024-23342 (ecdsa 0.19.1, Minerva timing attack, no fix available)
    — Transitive via python-jose. Not exploitable in our auth flow (we are
    on the *verifying* side; signature verification is unaffected per the
    advisory). Acknowledged and tracked.
"""
from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest import approx
from fastapi.testclient import TestClient

from platform_api.auth.dependencies import get_principal
from platform_api.auth.models import Principal
from platform_api.core.observability import SLO_LATENCY_P99_MS
from platform_api.db.session import get_db
from platform_api.main import create_app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PLATFORM_API_DIR = Path(__file__).parent.parent / "platform_api"
_REQUIREMENTS_FILE = Path(__file__).parent.parent / "requirements.txt"
_PYTHON = sys.executable

# Known CVEs that have been reviewed and accepted — no fix version available.
_ACCEPTED_CVES: dict[str, str] = {
    "CVE-2024-23342": (
        "ecdsa 0.19.1 — Minerva timing attack on P-256. Transitive via "
        "python-jose. Only signature *creation* is affected; we only *verify*. "
        "No fix available upstream. Will patch when fix released."
    ),
}


# ---------------------------------------------------------------------------
# 1. Security — bandit static analysis
# ---------------------------------------------------------------------------


def _run_bandit() -> dict:
    """Run bandit on platform_api/ and return the parsed JSON report."""
    result = subprocess.run(
        [_PYTHON, "-m", "bandit", "-r", str(_PLATFORM_API_DIR), "-f", "json", "-q"],
        capture_output=True,
        text=True,
    )
    # bandit exits non-zero when it finds issues; we parse regardless
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"bandit returned non-JSON output:\n{result.stdout}\n{result.stderr}")


def test_bandit_no_high_severity_findings():
    """Zero HIGH or CRITICAL severity findings in platform_api/."""
    report = _run_bandit()
    high_critical = [
        f
        for f in report.get("results", [])
        if f.get("issue_severity", "").upper() in ("HIGH", "CRITICAL")
    ]
    if high_critical:
        details = "\n".join(
            f"  [{f['issue_severity']}] {f['test_id']} {f['test_name']} "
            f"@ {f['filename']}:{f['line_number']}"
            for f in high_critical
        )
        pytest.fail(f"bandit found {len(high_critical)} HIGH/CRITICAL issue(s):\n{details}")


def test_bandit_medium_findings_are_expected():
    """MEDIUM findings must match the acknowledged list (B104 bind-all-interfaces)."""
    _EXPECTED_MEDIUM_TESTS = {"B104"}  # hardcoded bind to 0.0.0.0 — intentional default
    report = _run_bandit()
    medium = [
        f for f in report.get("results", [])
        if f.get("issue_severity", "").upper() == "MEDIUM"
    ]
    unexpected = [f for f in medium if f["test_id"] not in _EXPECTED_MEDIUM_TESTS]
    if unexpected:
        details = "\n".join(
            f"  [{f['issue_severity']}] {f['test_id']} {f['test_name']} "
            f"@ {f['filename']}:{f['line_number']}"
            for f in unexpected
        )
        pytest.fail(
            f"Unexpected MEDIUM bandit finding(s) — add to acknowledged list or fix them:\n{details}"
        )


def test_bandit_scan_completes_successfully():
    """bandit scan runs to completion without crashing."""
    report = _run_bandit()
    assert "results" in report
    assert "metrics" in report


# ---------------------------------------------------------------------------
# 2. Dependency audit — pip-audit
# ---------------------------------------------------------------------------


def _run_pip_audit() -> list[dict]:
    """Run pip-audit on requirements.txt and return list of vulnerable packages."""
    result = subprocess.run(
        [
            _PYTHON, "-m", "pip_audit",
            "--format", "json",
            "-r", str(_REQUIREMENTS_FILE),
        ],
        capture_output=True,
        text=True,
    )
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"pip-audit returned non-JSON:\n{result.stdout}\n{result.stderr}")

    # Collect all {package, cve_id} pairs with vulns
    findings = []
    for dep in report.get("dependencies", []):
        for vuln in dep.get("vulns", []):
            findings.append(
                {
                    "package": dep["name"],
                    "version": dep["version"],
                    "cve_id": vuln["id"],
                    "aliases": vuln.get("aliases", []),
                    "fix_versions": vuln.get("fix_versions", []),
                    "description": vuln.get("description", ""),
                }
            )
    return findings


def test_pip_audit_no_unacknowledged_cves():
    """All known CVEs must be in the _ACCEPTED_CVES allow-list."""
    findings = _run_pip_audit()
    unacknowledged = [
        f for f in findings if f["cve_id"] not in _ACCEPTED_CVES
    ]
    if unacknowledged:
        details = "\n".join(
            f"  [{f['cve_id']}] {f['package']}=={f['version']} — {f['description'][:120]}"
            for f in unacknowledged
        )
        pytest.fail(
            f"{len(unacknowledged)} unacknowledged CVE(s) — review and add to _ACCEPTED_CVES "
            f"or upgrade the affected package:\n{details}"
        )


def test_pip_audit_accepted_cves_have_no_fix():
    """Accepted CVEs must still have no fix version — if a fix ships, upgrade."""
    findings = _run_pip_audit()
    for finding in findings:
        if finding["cve_id"] in _ACCEPTED_CVES and finding["fix_versions"]:
            pytest.fail(
                f"A fix is now available for accepted CVE {finding['cve_id']} "
                f"({finding['package']} fix: {finding['fix_versions']}) — "
                f"please upgrade and remove from allow-list."
            )


def test_pip_audit_completes():
    """pip-audit scan runs without crashing."""
    findings = _run_pip_audit()
    assert isinstance(findings, list)


# ---------------------------------------------------------------------------
# 3. Performance — SLO latency assertions
# ---------------------------------------------------------------------------

_N_REQUESTS = 50


@pytest.fixture()
def _perf_client(seeded_db):
    """Per-test TestClient with auth for performance measurements."""
    app = create_app()
    user = seeded_db["user_admin"]
    principal = Principal(sub=user.sub, email=user.email, claims={})

    app.dependency_overrides[get_principal] = lambda: principal
    app.dependency_overrides[get_db] = lambda: (yield seeded_db["db"])

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, seeded_db


def _percentile(data: list[float], p: float) -> float:
    """Return the p-th percentile of data (0–100)."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = (p / 100) * (len(sorted_data) - 1)
    lower = int(idx)
    upper = min(lower + 1, len(sorted_data) - 1)
    return sorted_data[lower] + (idx - lower) * (sorted_data[upper] - sorted_data[lower])


def test_health_endpoint_p99_under_slo():
    """GET /healthz p99 latency must be under SLO_LATENCY_P99_MS within TestClient."""
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    latencies_ms = []
    for _ in range(_N_REQUESTS):
        t0 = time.perf_counter()
        r = client.get("/healthz")
        latencies_ms.append((time.perf_counter() - t0) * 1000)
        assert r.status_code == 200

    p99 = _percentile(latencies_ms, 99)
    p50 = _percentile(latencies_ms, 50)

    assert p99 < SLO_LATENCY_P99_MS, (
        f"/healthz p99={p99:.1f}ms exceeds SLO of {SLO_LATENCY_P99_MS}ms "
        f"(p50={p50:.1f}ms, max={max(latencies_ms):.1f}ms)"
    )


def test_list_workflows_p99_under_slo(_perf_client):
    """GET /v1/workflows p99 latency must be under SLO."""
    client, sdb = _perf_client
    ws_id = str(sdb["workspace"].id)

    latencies_ms = []
    for _ in range(_N_REQUESTS):
        t0 = time.perf_counter()
        r = client.get(f"/v1/workflows?workspace_id={ws_id}")
        latencies_ms.append((time.perf_counter() - t0) * 1000)
        assert r.status_code == 200

    p99 = _percentile(latencies_ms, 99)
    assert p99 < SLO_LATENCY_P99_MS, (
        f"GET /v1/workflows p99={p99:.1f}ms exceeds SLO of {SLO_LATENCY_P99_MS}ms"
    )


def test_create_workflow_p99_under_slo(_perf_client):
    """POST /v1/workflows p99 latency (draft create) must be under SLO."""
    client, sdb = _perf_client
    ws_id = str(sdb["workspace"].id)
    spec = {"steps": [{"id": "s1", "tool": "data_load"}]}

    latencies_ms = []
    with patch("platform_api.services.workflow_service.enforce_tenant_write_quota"):
        for i in range(_N_REQUESTS):
            t0 = time.perf_counter()
            r = client.post(
                "/v1/workflows",
                json={"workspace_id": ws_id, "name": f"perf-flow-{i}", "spec": spec, "publish": False},
            )
            latencies_ms.append((time.perf_counter() - t0) * 1000)
            assert r.status_code == 200

    p99 = _percentile(latencies_ms, 99)
    assert p99 < SLO_LATENCY_P99_MS, (
        f"POST /v1/workflows p99={p99:.1f}ms exceeds SLO of {SLO_LATENCY_P99_MS}ms"
    )


def test_p99_computation_correctness():
    """Unit test for the _percentile helper."""
    data = list(range(1, 101))  # 1..100
    assert _percentile(data, 50) == pytest.approx(50.5, abs=0.5)
    assert _percentile(data, 99) == pytest.approx(99.01, abs=0.5)
    assert _percentile(data, 100) == 100


def test_performance_report_printed(capsys, _perf_client):
    """Print a concise performance summary to stdout for CI logs."""
    client, sdb = _perf_client
    ws_id = str(sdb["workspace"].id)

    latencies_ms = []
    for _ in range(_N_REQUESTS):
        t0 = time.perf_counter()
        client.get(f"/v1/workflows?workspace_id={ws_id}")
        latencies_ms.append((time.perf_counter() - t0) * 1000)

    p50 = _percentile(latencies_ms, 50)
    p95 = _percentile(latencies_ms, 95)
    p99 = _percentile(latencies_ms, 99)
    mean = statistics.mean(latencies_ms)

    print(
        f"\n[Performance] GET /v1/workflows ({_N_REQUESTS} requests)\n"
        f"  mean={mean:.2f}ms  p50={p50:.2f}ms  p95={p95:.2f}ms  p99={p99:.2f}ms\n"
        f"  SLO p99 budget: {SLO_LATENCY_P99_MS}ms  {'✅ PASS' if p99 < SLO_LATENCY_P99_MS else '❌ FAIL'}"
    )
    assert True  # Always passes; this test just surfaces the numbers
