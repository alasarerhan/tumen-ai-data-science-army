from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERNS = [
    re.compile(r"\bsk-(?!\.\.\.|example|test|redacted)[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bsk-proj-(?!\.\.\.|example|test|redacted)[A-Za-z0-9_-]{20,}\b"),
]
SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
    ".zip",
    ".gz",
    ".db",
    ".sqlite",
    ".sqlite3",
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [ROOT / line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    findings: list[str] = []
    for path in tracked_files():
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if any(pattern.search(line) for pattern in SECRET_PATTERNS):
                relative = path.relative_to(ROOT).as_posix()
                findings.append(f"{relative}:{line_number}")
    if findings:
        print("Potential tracked secret values found:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("No tracked OpenAI-style secret values found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
