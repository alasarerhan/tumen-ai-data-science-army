"""Soak monitor — RSS, fd count, thread count örnekleme.

Kanban 4.2. psutil ile her dakika uvicorn process örneği.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path


def sample_process(pid: int) -> dict:
    """Bir PID için RSS/fd/thread örneği (psutil yoksa /proc üzerinden)."""
    sample = {"pid": pid, "ts": time.time()}
    try:
        # macOS: psutil yerine ps + lsof
        ps = subprocess.run(
            ["ps", "-o", "rss=,vsz=,pid=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if ps.returncode == 0:
            line = ps.stdout.strip().splitlines()[-1].split()
            if len(line) >= 2:
                sample["rss_kb"] = int(line[0])
                sample["vsz_kb"] = int(line[1])

        # fd count (macOS)
        fd_proc = subprocess.run(
            ["lsof", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if fd_proc.returncode == 0:
            sample["fd_count"] = len(fd_proc.stdout.strip().splitlines()) - 1

        # thread count (ps -M)
        mac_proc = subprocess.run(
            ["ps", "-M", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if mac_proc.returncode == 0:
            # İlk satır header, kalanı thread
            sample["thread_count"] = len(mac_proc.stdout.strip().splitlines()) - 1
    except Exception as exc:
        sample["error"] = str(exc)
    return sample


def run_monitor(
    pid: int,
    duration_seconds: int,
    interval: int = 60,
    output_path: Path = Path("soak_samples.jsonl"),
):
    """Belirli süre boyunca örnekleme yap, JSONL dosyasına yaz."""
    print(f"Starting soak monitor for PID={pid} duration={duration_seconds}s interval={interval}s")
    samples = []
    deadline = time.time() + duration_seconds
    sample_num = 0
    while time.time() < deadline:
        s = sample_process(pid)
        samples.append(s)
        sample_num += 1
        with open(output_path, "a") as f:
            f.write(json.dumps(s) + "\n")
        if sample_num % 5 == 0:
            print(f"  {sample_num} samples collected")
        time.sleep(interval)
    print(f"Soak monitor complete: {sample_num} samples → {output_path}")
    return samples


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python tools/soak_monitor.py <pid> <duration_seconds>")
        sys.exit(1)
    pid = int(sys.argv[1])
    duration = int(sys.argv[2])
    run_monitor(pid, duration)
