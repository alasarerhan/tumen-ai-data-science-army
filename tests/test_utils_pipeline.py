from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


@pytest.fixture(scope="module")
def pipeline_module() -> ModuleType:
    module_path = (
        Path(__file__).resolve().parents[1] / "ai_data_science_team" / "utils" / "pipeline.py"
    )
    spec = importlib.util.spec_from_file_location("pipeline_utils_under_test", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def readable_text_file(tmp_path: Path) -> Path:
    path = tmp_path / "transform.py"
    path.write_text("def transform(df):\n    return df\n", encoding="utf-8")
    yield path


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (None, ""),
        ("", ""),
        ("   ", ""),
        ("print(1)", "print(1)"),
        ("```python\nx = 'ğüşöçıİ 🚀'\n```", "x = 'ğüşöçıİ 🚀'"),
        ("```\n  x = 1  \n```", "x = 1"),
        ("x" * 10_001, "x" * 10_001),
    ],
)
def test_strip_markdown_code_fences_handles_text_boundaries(
    pipeline_module: ModuleType,
    code: Any,
    expected: str,
) -> None:
    # Arrange
    # Act
    result = pipeline_module.strip_markdown_code_fences(code)

    # Assert
    assert result == expected


@pytest.mark.parametrize(
    ("value", "default", "expected"),
    [
        (0, 9.0, 0.0),
        (-1, 9.0, -1.0),
        (sys.maxsize, 9.0, float(sys.maxsize)),
        (10**100, 9.0, float(10**100)),
        ("3.25", 9.0, 3.25),
        (None, 7.5, 7.5),
        ("", 7.5, 7.5),
        ([], 7.5, 7.5),
        ({}, 7.5, 7.5),
        (set(), 7.5, 7.5),
        (tuple(), 7.5, 7.5),
    ],
)
def test_as_float_handles_numeric_and_empty_values(
    pipeline_module: ModuleType,
    value: Any,
    default: float,
    expected: float,
) -> None:
    # Arrange
    # Act
    result = pipeline_module._as_float(value, default=default)

    # Assert
    assert result == pytest.approx(expected)


@pytest.mark.parametrize("value", [float("inf"), float("-inf")])
def test_as_float_preserves_infinities(pipeline_module: ModuleType, value: float) -> None:
    # Arrange
    # Act
    result = pipeline_module._as_float(value)

    # Assert
    assert math.isinf(result)
    assert result == value


def test_as_float_preserves_nan(pipeline_module: ModuleType) -> None:
    # Arrange
    # Act
    result = pipeline_module._as_float(float("nan"))

    # Assert
    assert math.isnan(result)


def test_pick_latest_dataset_id_filters_stage_and_uses_last_tie(
    pipeline_module: ModuleType,
) -> None:
    # Arrange
    datasets = {
        "ignored": [],
        "old": {"stage": "feature", "created_ts": "1"},
        "other_stage": {"stage": "model", "created_ts": "100"},
        "tie_a": {"stage": "feature", "created_ts": 2},
        "tie_b": {"stage": "feature", "created_ts": 2},
    }

    # Act
    result = pipeline_module.pick_latest_dataset_id(datasets, stage="feature")

    # Assert
    assert result == "tie_b"


@pytest.mark.parametrize(
    ("datasets", "stage", "expected"),
    [
        (None, "feature", None),
        ({}, "feature", None),
        ({"a": {"stage": "raw", "created_ts": 1}}, "feature", None),
        ({"a": {"stage": "feature", "created_ts": "bad"}}, "feature", "a"),
    ],
)
def test_pick_latest_dataset_id_handles_empty_and_invalid_inputs(
    pipeline_module: ModuleType,
    datasets: Any,
    stage: str,
    expected: str | None,
) -> None:
    # Arrange
    # Act
    result = pipeline_module.pick_latest_dataset_id(datasets, stage=stage)

    # Assert
    assert result == expected


def test_pick_latest_dataset_id_any_stage_ignores_non_dict_entries(
    pipeline_module: ModuleType,
) -> None:
    # Arrange
    datasets = {
        "empty": {},
        "bad": "not-a-dataset",
        "first": {"created_ts": -1},
        "latest": {"created_ts": "9"},
    }

    # Act
    result = pipeline_module.pick_latest_dataset_id_any_stage(datasets)

    # Assert
    assert result == "latest"


@pytest.mark.parametrize(
    ("datasets", "target", "expected"),
    [
        ({}, "x", []),
        (None, "x", []),
        ({"root": {"parent_id": None}}, "", []),
        ({"root": {"parent_id": None}, "child": {"parent_id": "root"}}, "child", ["root", "child"]),
        ({"a": {"parent_id": "b"}, "b": {"parent_id": "a"}}, "a", ["b", "a"]),
        ({"a": {"parent_id": "missing"}}, "a", ["a"]),
    ],
)
def test_build_dataset_lineage_ids_handles_roots_cycles_and_missing_links(
    pipeline_module: ModuleType,
    datasets: Any,
    target: str,
    expected: list[str],
) -> None:
    # Arrange
    # Act
    result = pipeline_module.build_dataset_lineage_ids(datasets, target)

    # Assert
    assert result == expected


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        ({}, []),
        ([], []),
        ({"parent_id": ""}, []),
        ({"parent_id": "p0"}, ["p0"]),
        ({"parent_ids": ["p1", "p0", "p1"], "parent_id": "p0"}, ["p1", "p0"]),
        ({"parent_ids": ("frozen",), "parent_id": "single"}, ["single"]),
        ({"parent_ids": ["ğüşöçıİ", "emoji-🚀"]}, ["ğüşöçıİ", "emoji-🚀"]),
    ],
)
def test_parent_ids_normalizes_parent_shapes(
    pipeline_module: ModuleType,
    entry: Any,
    expected: list[str],
) -> None:
    # Arrange
    # Act
    result = pipeline_module._parent_ids(entry)

    # Assert
    assert result == expected


def test_build_dataset_dag_ids_orders_parents_before_merge_child(
    pipeline_module: ModuleType,
) -> None:
    # Arrange
    datasets = {
        "root": {},
        "left": {"parent_id": "root"},
        "right": {"parent_id": "root"},
        "merge": {"parent_ids": ["left", "right"]},
    }

    # Act
    result = pipeline_module.build_dataset_dag_ids(datasets, "merge")

    # Assert
    assert result == ["root", "left", "right", "merge"]


def test_build_dataset_dag_ids_handles_cycles_without_recursing_forever(
    pipeline_module: ModuleType,
) -> None:
    # Arrange
    datasets = {"a": {"parent_id": "b"}, "b": {"parent_id": "a"}}

    # Act
    result = pipeline_module.build_dataset_dag_ids(datasets, "a")

    # Assert
    assert result == ["b", "a"]


def test_compute_pipeline_hash_prefers_stable_dataset_properties(
    pipeline_module: ModuleType,
) -> None:
    # Arrange
    first = {
        "session-id-1": {
            "stage": "raw",
            "label": "Orders",
            "fingerprint": "fp-root",
            "provenance": {"source_type": "file", "source": "orders.csv"},
        },
        "session-id-2": {
            "stage": "feature",
            "label": "Features",
            "parent_id": "session-id-1",
            "schema_hash": "schema-feature",
            "provenance": {"transform": {"kind": "python_function", "code_sha256": "abc"}},
        },
    }
    second = {
        "new-id-1": {
            "stage": "raw",
            "label": "Orders",
            "fingerprint": "fp-root",
            "provenance": {"source_type": "file", "source": "orders.csv"},
        },
        "new-id-2": {
            "stage": "feature",
            "label": "Features",
            "parent_id": "new-id-1",
            "schema_hash": "schema-feature",
            "provenance": {"transform": {"kind": "python_function", "code_sha256": "abc"}},
        },
    }

    # Act
    first_hash = pipeline_module.compute_pipeline_hash(first, ["session-id-1", "session-id-2"])
    second_hash = pipeline_module.compute_pipeline_hash(second, ["new-id-1", "new-id-2"])

    # Assert
    assert first_hash == second_hash
    assert isinstance(first_hash, str)
    assert len(first_hash) == 64


@pytest.mark.parametrize(
    ("datasets", "lineage_ids", "expected"),
    [
        ({}, [], None),
        (None, ["a"], None),
    ],
)
def test_compute_pipeline_hash_returns_none_for_missing_inputs(
    pipeline_module: ModuleType,
    datasets: Any,
    lineage_ids: list[str],
    expected: None,
) -> None:
    # Arrange
    # Act
    result = pipeline_module.compute_pipeline_hash(datasets, lineage_ids)

    # Assert
    assert result is expected


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("def transform(df):\n    return df", "transform"),
        ("\n    def spaced_name():\n        return 1", "spaced_name"),
        ("async def ignored():\n    return 1", None),
        ("def ğüş(df):\n    return df", None),
        ("", None),
        (None, None),
    ],
)
def test_infer_function_name_handles_python_def_boundaries(
    pipeline_module: ModuleType,
    code: Any,
    expected: str | None,
) -> None:
    # Arrange
    # Act
    result = pipeline_module._infer_function_name(code)

    # Assert
    assert result == expected


def test_read_text_file_handles_existing_missing_and_size_limits(
    pipeline_module: ModuleType,
    readable_text_file: Path,
    tmp_path: Path,
) -> None:
    # Arrange
    large_file = tmp_path / "large.py"
    large_file.write_text("x" * 20, encoding="utf-8")

    # Act
    existing = pipeline_module._read_text_file(str(readable_text_file))
    missing = pipeline_module._read_text_file(str(tmp_path / "missing.py"))
    empty_path = pipeline_module._read_text_file("")
    too_large = pipeline_module._read_text_file(str(large_file), max_bytes=10)

    # Assert
    assert existing == "def transform(df):\n    return df\n"
    assert missing is None
    assert empty_path is None
    assert too_large is None


def test_script_append_helpers_add_header_footer_and_metadata(pipeline_module: ModuleType) -> None:
    # Arrange
    lines: list[str] = []

    # Act
    pipeline_module._append_script_header(lines, target_dataset_id="target-1")
    pipeline_module._append_step_metadata(
        lines,
        step_number=1,
        dataset_id="dataset-1",
        entry={
            "stage": "feature",
            "label": "Feature set",
            "schema_hash": "schema-1",
            "fingerprint": "fp-1",
        },
        transform={"kind": "python_function", "code_sha256": "code-1", "sql_sha256": "sql-1"},
    )
    pipeline_module._append_sql_loader_lines(lines, df_var="df", sql_query="SELECT 1")
    pipeline_module._append_script_footer(lines)

    # Assert
    assert "# Target dataset id: target-1" in lines
    assert "import pandas as pd" in lines
    assert "# Step 1: feature - Feature set (dataset-1)" in lines
    assert "#   schema_hash: schema-1" in lines
    assert "sql_query = 'SELECT 1'" in lines
    assert "print('Final shape:', getattr(df, 'shape', None))" in lines


@pytest.mark.parametrize(
    ("provenance", "label", "expected"),
    [
        ({"source": "sales.csv"}, "fallback.csv", "sales.csv"),
        ({"source": " load_file ", "original_name": "raw.tsv"}, "fallback.csv", "raw.tsv"),
        ({"source": "artifact", "original_name": "load_file_abc"}, "actual.xlsx", "actual.xlsx"),
        ({"source": ""}, "  ", None),
        ({}, "ğüşöçıİ.csv", "ğüşöçıİ.csv"),
    ],
)
def test_pick_file_source_uses_first_real_source(
    pipeline_module: ModuleType,
    provenance: dict[str, Any],
    label: str,
    expected: str | None,
) -> None:
    # Arrange
    # Act
    result = pipeline_module._pick_file_source(provenance, label=label)

    # Assert
    assert result == expected


@pytest.mark.parametrize(
    ("source", "expected_line"),
    [
        ("data.csv", "df = pd.read_csv('data.csv')"),
        ("data.csv.gz", "df = pd.read_csv('data.csv.gz')"),
        ("data.tsv", "df = pd.read_csv('data.tsv', sep='\\t')"),
        ("data.parquet", "df = pd.read_parquet('data.parquet')"),
        ("data.jsonl", "df = pd.read_json('data.jsonl')"),
        ("data.xlsx", "df = pd.read_excel('data.xlsx')"),
        ("data.unknown", "df = pd.read_csv('data.unknown')"),
    ],
)
def test_append_root_source_lines_emits_reader_for_file_types(
    pipeline_module: ModuleType,
    source: str,
    expected_line: str,
) -> None:
    # Arrange
    lines: list[str] = []

    # Act
    pipeline_module._append_root_source_lines(
        lines,
        df_var="df",
        stage="raw",
        provenance={"source_type": "file", "source": source},
        transform={},
        label="fallback.csv",
        missing_source_todo="# TODO",
    )

    # Assert
    assert expected_line in lines


@pytest.mark.parametrize(
    ("stage", "provenance", "transform", "expected_line"),
    [
        (
            "sql",
            {},
            {"sql_query_code": "SELECT * FROM orders"},
            "df = pd.read_sql_query(sql_query, engine)",
        ),
        ("raw", {}, {}, "df = pd.DataFrame()"),
    ],
)
def test_append_root_source_lines_handles_sql_and_missing_sources(
    pipeline_module: ModuleType,
    stage: str,
    provenance: dict[str, Any],
    transform: dict[str, Any],
    expected_line: str,
) -> None:
    # Arrange
    lines: list[str] = []

    # Act
    pipeline_module._append_root_source_lines(
        lines,
        df_var="df",
        stage=stage,
        provenance=provenance,
        transform=transform,
        label="",
        missing_source_todo="# TODO missing",
    )

    # Assert
    assert expected_line in lines


@pytest.mark.parametrize(
    ("transform", "expected_snippet"),
    [
        (
            {
                "kind": "python_function",
                "function_code": "```python\ndef transform(df):\n    return df\n```",
            },
            "df = transform(df)",
        ),
        (
            {"kind": "sql_query", "sql_query_code": "SELECT 1"},
            "df = pd.read_sql_query(sql_query, engine)",
        ),
        ({"kind": "mlflow_predict", "run_id": "run-1"}, "model_uri = 'runs:/run-1/model'"),
        ({"kind": "h2o_predict", "model_id": "model-1"}, "model = h2o.get_model('model-1')"),
        (
            {"kind": "unknown"},
            "# TODO: transform not recorded in a runnable form; see datasets provenance.",
        ),
        (
            {"kind": "python_function"},
            "# TODO: missing function code/name for this step; see datasets provenance.",
        ),
    ],
)
def test_append_transform_lines_emits_runnable_transform_stubs(
    pipeline_module: ModuleType,
    transform: dict[str, Any],
    expected_snippet: str,
) -> None:
    # Arrange
    lines: list[str] = []

    # Act
    pipeline_module._append_transform_lines(lines, df_var="df", transform=transform)

    # Assert
    assert expected_snippet in lines


def test_append_transform_lines_prefers_function_file(
    pipeline_module: ModuleType,
    readable_text_file: Path,
) -> None:
    # Arrange
    lines: list[str] = []

    # Act
    pipeline_module._append_transform_lines(
        lines,
        df_var="df",
        transform={"kind": "python_function", "function_path": str(readable_text_file)},
    )

    # Assert
    assert "def transform(df):\n    return df" in lines
    assert "df = transform(df)" in lines


def test_build_chain_lines_combines_metadata_source_and_transform_steps(
    pipeline_module: ModuleType,
) -> None:
    # Arrange
    datasets = {
        "root": {
            "stage": "raw",
            "label": "orders.csv",
            "provenance": {"source_type": "file", "source": "orders.csv"},
        },
        "feature": {
            "stage": "feature",
            "label": "features",
            "parent_id": "root",
            "provenance": {
                "transform": {
                    "kind": "python_function",
                    "function_code": "def transform(df):\n    return df",
                }
            },
        },
    }

    # Act
    lines = pipeline_module._build_chain_lines(
        datasets,
        ["root", "feature"],
        df_var="df",
        missing_source_todo="# TODO missing",
    )

    # Assert
    assert "df = None" in lines
    assert "df = pd.read_csv('orders.csv')" in lines
    assert "df = transform(df)" in lines


def test_build_reproducible_pipeline_script_generates_single_lineage_script(
    pipeline_module: ModuleType,
) -> None:
    # Arrange
    datasets = {
        "root": {
            "stage": "raw",
            "label": "orders.csv",
            "provenance": {"source_type": "file", "source": "orders.csv"},
        },
        "feature": {
            "stage": "feature",
            "label": "features",
            "parent_id": "root",
            "provenance": {
                "transform": {
                    "kind": "python_function",
                    "function_name": "make_features",
                    "function_code": "def make_features(df):\n    return df",
                }
            },
        },
    }

    # Act
    script = pipeline_module.build_reproducible_pipeline_script(
        datasets,
        target_dataset_id="feature",
    )

    # Assert
    assert "# Target dataset id: feature" in script
    assert "df = pd.read_csv('orders.csv')" in script
    assert "df = make_features(df)" in script
    assert script.endswith("\n")


def test_build_reproducible_pipeline_script_generates_merge_branches(
    pipeline_module: ModuleType,
) -> None:
    # Arrange
    datasets = {
        "left": {"label": "left.csv", "provenance": {"source_type": "file", "source": "left.csv"}},
        "right": {
            "label": "right.csv",
            "provenance": {"source_type": "file", "source": "right.csv"},
        },
        "merge": {
            "parent_ids": ["left", "right"],
            "provenance": {
                "transform": {
                    "kind": "python_merge",
                    "merge_code": "df = df_0.merge(df_1, on='id')",
                }
            },
        },
    }

    # Act
    script = pipeline_module.build_reproducible_pipeline_script(datasets, target_dataset_id="merge")

    # Assert
    assert "# --- Branch 1: parent left ---" in script
    assert "# --- Branch 2: parent right ---" in script
    assert "df = df_0.merge(df_1, on='id')" in script


@pytest.mark.parametrize(
    ("target", "expected_target", "expected_dataset_id", "expected_lineage"),
    [
        ("model", "model", "feature", ["root", "feature"]),
        ("active", "active", "root", ["root"]),
        ("latest", "latest", "model", ["root", "feature", "model"]),
        ("all", "all", None, ["root", "feature", "model"]),
        (" whitespace ", "model", "feature", ["root", "feature"]),
    ],
)
def test_build_pipeline_snapshot_selects_target_and_lineage(
    pipeline_module: ModuleType,
    target: str,
    expected_target: str,
    expected_dataset_id: str | None,
    expected_lineage: list[str],
) -> None:
    # Arrange
    datasets = {
        "root": {
            "stage": "raw",
            "label": "orders.csv",
            "created_ts": 1,
            "provenance": {"source_type": "file", "source": "orders.csv"},
        },
        "feature": {
            "stage": "feature",
            "label": "features",
            "parent_id": "root",
            "created_ts": 2,
            "provenance": {"transform": {"kind": "python_function", "code_sha256": "abc"}},
        },
        "model": {
            "stage": "model",
            "label": "model",
            "parent_id": "feature",
            "created_ts": 3,
            "provenance": {"transform": {"kind": "mlflow_predict", "run_id": "run-1"}},
        },
    }

    # Act
    snapshot = pipeline_module.build_pipeline_snapshot(
        datasets,
        active_dataset_id="root",
        target=target,
    )

    # Assert
    assert snapshot["target"] == expected_target
    assert snapshot["target_dataset_id"] == expected_dataset_id
    assert [entry["id"] for entry in snapshot["lineage"]] == expected_lineage


def test_build_pipeline_snapshot_returns_empty_defaults_for_invalid_inputs(
    pipeline_module: ModuleType,
) -> None:
    # Arrange
    # Act
    snapshot = pipeline_module.build_pipeline_snapshot(None, active_dataset_id=None)

    # Assert
    assert snapshot["pipeline_hash"] is None
    assert snapshot["target_dataset_id"] is None
    assert snapshot["lineage"] == []
    assert snapshot["script"] == ""
