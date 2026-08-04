#!/usr/bin/env python3
"""Baseline maintainability metrics for phased refactor tracking.

Computes:
- files with more than N lines (default 400)
- functions with more than N lines (default 40)
- hotspots with nesting depth greater than N (default 3)
- duplicate normalized code blocks (default block size 6 lines)
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

SUPPORTED_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx"}
DEFAULT_EXCLUDES = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".pip-cache",
    ".codex",
}

FUNCTION_SIGNATURE_RE = re.compile(r"^\s*(export\s+)?(async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(")
ASSIGNMENT_FUNCTION_RE = re.compile(
    r"^\s*(export\s+)?(const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(async\s*)?\("
)
ASSIGNMENT_ARROW_RE = re.compile(
    r"^\s*(export\s+)?(const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(async\s*)?[^=]*=>"
)


@dataclass
class FunctionMetric:
    file: str
    name: str
    start_line: int
    end_line: int
    lines: int
    language: str


@dataclass
class NestingMetric:
    file: str
    max_depth: int
    language: str


def iter_source_files(root: Path, excludes: set[str]) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in SUPPORTED_SUFFIXES:
            continue
        parts = set(path.parts)
        if parts & excludes:
            continue
        yield path


def file_line_count(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="ignore")
    return len(text.splitlines())


def extract_python_functions(path: Path) -> list[FunctionMetric]:
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        source = path.read_text(encoding="utf-8", errors="ignore")

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    functions: list[FunctionMetric] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not hasattr(node, "end_lineno") or node.end_lineno is None:
            continue
        start = node.lineno
        end = int(node.end_lineno)
        functions.append(
            FunctionMetric(
                file=str(path),
                name=node.name,
                start_line=start,
                end_line=end,
                lines=end - start + 1,
                language="python",
            )
        )
    return functions


def _scan_until_block_start(lines: list[str], start_index: int) -> int | None:
    for i in range(start_index, min(start_index + 6, len(lines))):
        if "{" in lines[i]:
            return i
    return None


def extract_ts_like_functions(path: Path) -> list[FunctionMetric]:
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        source = path.read_text(encoding="utf-8", errors="ignore")

    lines = source.splitlines()
    functions: list[FunctionMetric] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        name = None
        if m := FUNCTION_SIGNATURE_RE.match(line):
            name = m.group(3)
        elif m := ASSIGNMENT_FUNCTION_RE.match(line):
            name = m.group(3)
        elif m := ASSIGNMENT_ARROW_RE.match(line):
            name = m.group(3)

        if not name:
            i += 1
            continue

        open_line_index = _scan_until_block_start(lines, i)
        if open_line_index is None:
            i += 1
            continue

        depth = 0
        end_index = None
        for j in range(open_line_index, len(lines)):
            depth += lines[j].count("{")
            depth -= lines[j].count("}")
            if depth == 0 and j >= open_line_index:
                end_index = j
                break
        if end_index is None:
            i += 1
            continue

        start_line = i + 1
        end_line = end_index + 1
        functions.append(
            FunctionMetric(
                file=str(path),
                name=name,
                start_line=start_line,
                end_line=end_line,
                lines=end_line - start_line + 1,
                language="ts-like",
            )
        )
        i = end_index + 1
    return functions


def python_nesting_depth(path: Path) -> NestingMetric | None:
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        source = path.read_text(encoding="utf-8", errors="ignore")

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    control_nodes = (
        ast.If,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.With,
        ast.AsyncWith,
        ast.Try,
        ast.Match,
    )

    def walk(node: ast.AST, depth: int) -> int:
        child_depth = depth
        if isinstance(node, control_nodes):
            child_depth = depth + 1
        max_depth = child_depth
        for child in ast.iter_child_nodes(node):
            max_depth = max(max_depth, walk(child, child_depth))
        return max_depth

    return NestingMetric(file=str(path), max_depth=walk(tree, 0), language="python")


def ts_like_nesting_depth(path: Path) -> NestingMetric:
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        source = path.read_text(encoding="utf-8", errors="ignore")

    lines = source.splitlines()
    max_depth = 0
    current = 0
    control_re = re.compile(r"\b(if|for|while|switch|try|catch)\b")
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        opens = line.count("{")
        closes = line.count("}")
        if control_re.search(stripped):
            current += 1
            max_depth = max(max_depth, current)
        current += opens - closes
        if current < 0:
            current = 0
    return NestingMetric(file=str(path), max_depth=max_depth, language="ts-like")


def normalize_for_dup(line: str) -> str:
    compact = re.sub(r"\s+", " ", line.strip())
    compact = re.sub(r"['\"][^'\"]*['\"]", '"STR"', compact)
    compact = re.sub(r"\b\d+\b", "NUM", compact)
    return compact


def find_duplicate_blocks(files: list[Path], block_size: int) -> list[dict]:
    block_map: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()

        normalized = [normalize_for_dup(line) for line in lines]
        for i in range(0, len(normalized) - block_size + 1):
            window = normalized[i : i + block_size]
            if any(not part for part in window):
                continue
            block = "\n".join(window)
            block_hash = hashlib.sha1(block.encode("utf-8")).hexdigest()
            block_map[block_hash].append((str(path), i + 1, block))

    duplicates: list[dict] = []
    for _, occurrences in block_map.items():
        if len(occurrences) < 2:
            continue
        sample_file, sample_line, sample = occurrences[0]
        duplicates.append(
            {
                "occurrences": len(occurrences),
                "sample_file": sample_file,
                "sample_line": sample_line,
                "sample": sample,
                "locations": [{"file": f, "line": ln} for (f, ln, _) in occurrences[:10]],
            }
        )
    duplicates.sort(key=lambda item: item["occurrences"], reverse=True)
    return duplicates


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--max-file-lines", type=int, default=400)
    parser.add_argument("--max-function-lines", type=int, default=40)
    parser.add_argument("--max-nesting", type=int, default=3)
    parser.add_argument("--duplicate-block-size", type=int, default=6)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    files = list(iter_source_files(root, DEFAULT_EXCLUDES))

    large_files = []
    long_functions: list[FunctionMetric] = []
    deep_nesting: list[NestingMetric] = []
    for path in files:
        line_count = file_line_count(path)
        if line_count > args.max_file_lines:
            large_files.append({"file": str(path), "lines": line_count})

        if path.suffix == ".py":
            long_functions.extend(extract_python_functions(path))
            nesting = python_nesting_depth(path)
            if nesting:
                deep_nesting.append(nesting)
        else:
            long_functions.extend(extract_ts_like_functions(path))
            deep_nesting.append(ts_like_nesting_depth(path))

    long_functions = [fn for fn in long_functions if fn.lines > args.max_function_lines]
    deep_nesting = [n for n in deep_nesting if n.max_depth > args.max_nesting]

    large_files.sort(key=lambda item: item["lines"], reverse=True)
    long_functions.sort(key=lambda item: item.lines, reverse=True)
    deep_nesting.sort(key=lambda item: item.max_depth, reverse=True)

    duplicates = find_duplicate_blocks(files, args.duplicate_block_size)

    result = {
        "root": str(root),
        "thresholds": {
            "max_file_lines": args.max_file_lines,
            "max_function_lines": args.max_function_lines,
            "max_nesting": args.max_nesting,
            "duplicate_block_size": args.duplicate_block_size,
        },
        "counts": {
            "scanned_files": len(files),
            "files_gt_max": len(large_files),
            "functions_gt_max": len(long_functions),
            "nesting_gt_max": len(deep_nesting),
            "duplicate_blocks": len(duplicates),
        },
        "files_gt_max": large_files[:200],
        "functions_gt_max": [
            {
                "file": f.file,
                "name": f.name,
                "start_line": f.start_line,
                "end_line": f.end_line,
                "lines": f.lines,
                "language": f.language,
            }
            for f in long_functions[:300]
        ],
        "nesting_gt_max": [
            {"file": n.file, "max_depth": n.max_depth, "language": n.language}
            for n in deep_nesting[:300]
        ],
        "duplicate_blocks": duplicates[:100],
    }

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    print("Maintainability Baseline")
    print(f"Root: {result['root']}")
    print(f"Scanned files: {result['counts']['scanned_files']}")
    print(f"Files > {args.max_file_lines} lines: {result['counts']['files_gt_max']}")
    print(f"Functions > {args.max_function_lines} lines: {result['counts']['functions_gt_max']}")
    print(f"Nesting > {args.max_nesting}: {result['counts']['nesting_gt_max']}")
    print(
        f"Duplicate blocks ({args.duplicate_block_size} lines): "
        f"{result['counts']['duplicate_blocks']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
