from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class Probe:
    path: str
    expected_content_type: str | None = None


PROBES = (
    Probe("/healthz"),
    Probe("/ready"),
    Probe("/metrics", "text/plain"),
)


def request(base_url: str, probe: Probe) -> None:
    request = urllib.request.Request(f"{base_url.rstrip('/')}{probe.path}")
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status != 200:
            raise RuntimeError(f"{probe.path} returned HTTP {response.status}")
        content_type = response.headers.get_content_type()
        if probe.expected_content_type and content_type != probe.expected_content_type:
            raise RuntimeError(
                f"{probe.path} returned {content_type}, expected {probe.expected_content_type}"
            )
        payload = response.read()
        if not payload:
            raise RuntimeError(f"{probe.path} returned an empty response")
        if probe.path != "/metrics":
            body = json.loads(payload)
            if body.get("status") != "ok":
                raise RuntimeError(f"{probe.path} reported unhealthy state: {body}")


def compose(*args: str) -> str:
    result = subprocess.run(
        ["docker", "compose", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def wait_for_api(base_url: str, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            request(base_url, PROBES[0])
            return
        except (OSError, RuntimeError, urllib.error.URLError):
            time.sleep(2)
    raise RuntimeError(f"API did not become healthy within {timeout_seconds} seconds")


def verify_scheduler_logs() -> None:
    logs = compose("logs", "--no-color", "api")
    if "Scheduler started successfully" not in logs:
        raise RuntimeError("API logs do not prove that the scheduler started")
    premature_shutdown_markers = (
        "Scheduler startup skipped for app factory instance",
        "Application shutting down",
        "Shutdown complete",
    )
    found = [marker for marker in premature_shutdown_markers if marker in logs]
    if found:
        raise RuntimeError(f"API logs contain premature shutdown markers: {found}")


def verify_migration_head() -> None:
    current = compose("exec", "-T", "api", "alembic", "current").strip()
    heads = compose("exec", "-T", "api", "alembic", "heads").strip()
    if "(head)" not in current:
        raise RuntimeError(f"database is not at an Alembic head: {current!r}")
    current_revision = current.split()[0]
    head_revision = heads.split()[0] if heads else ""
    if not head_revision or current_revision != head_revision:
        raise RuntimeError(
            f"database revision {current_revision!r} does not match Alembic head {head_revision!r}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the real local Postgres/Redis stack and soak the API."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--duration-seconds", type=int, default=1800)
    parser.add_argument("--interval-seconds", type=int, default=30)
    parser.add_argument("--startup-timeout-seconds", type=int, default=180)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.duration_seconds < 1 or args.interval_seconds < 1:
        raise ValueError("duration and interval must be positive")

    wait_for_api(args.base_url, args.startup_timeout_seconds)
    verify_migration_head()
    verify_scheduler_logs()

    started_at = time.monotonic()
    deadline = started_at + args.duration_seconds
    probe_count = 0
    while True:
        for probe in PROBES:
            request(args.base_url, probe)
        probe_count += 1
        elapsed = time.monotonic() - started_at
        print(f"soak probe {probe_count} passed at {elapsed:.1f}s", flush=True)
        if time.monotonic() >= deadline:
            break
        time.sleep(min(args.interval_seconds, max(0.0, deadline - time.monotonic())))

    verify_scheduler_logs()
    print(
        f"local stack verification passed: {probe_count} probe cycles over "
        f"{time.monotonic() - started_at:.1f}s"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        OSError,
        RuntimeError,
        ValueError,
        subprocess.CalledProcessError,
        urllib.error.URLError,
    ) as exc:
        print(f"local stack verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
