"""Audit log retention — 90 gün default.

Kanban 7.3. tools/audit_cleanup.py: 90 günden eski entry'leri arşive taşı.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path


def cleanup(log_dir: Path, retention_days: int = 90, archive_dir: Path | None = None):
    """90 günden eski audit log'ları arşive taşı."""
    if archive_dir is None:
        archive_dir = log_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - (retention_days * 86400)
    moved = 0
    for log_file in log_dir.glob("*.log"):
        if log_file.stat().st_mtime < cutoff:
            target = archive_dir / log_file.name
            shutil.move(str(log_file), str(target))
            moved += 1
    for json_file in log_dir.glob("*.json"):
        if json_file.stat().st_mtime < cutoff:
            target = archive_dir / json_file.name
            shutil.move(str(json_file), str(target))
            moved += 1
    return {"moved": moved, "archive_dir": str(archive_dir), "cutoff_days": retention_days}


if __name__ == "__main__":
    import sys

    log_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/audit_test")
    log_dir.mkdir(parents=True, exist_ok=True)
    # Test fixture: 100 gün önce eski dosya
    old = log_dir / "old_audit.json"
    old.write_text(json.dumps({"timestamp": "2025-01-01", "action": "test"}))
    old_time = time.time() - (100 * 86400)
    os.utime(old, (old_time, old_time))
    # Yeni dosya (korumalı)
    new = log_dir / "new_audit.json"
    new.write_text(json.dumps({"timestamp": "2026-08-03", "action": "test"}))
    result = cleanup(log_dir, retention_days=90)
    print(json.dumps(result, indent=2))
    print(f"old exists: {old.exists()} (should be False)")
    print(f"new exists: {new.exists()} (should be True)")
    # Cleanup test dir
    shutil.rmtree(log_dir)
