import pandas as pd
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "apps" / "ai-pipeline-studio-app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from pipeline_studio_runtime import (
    _apply_branch_ui_action,
    _build_children_index,
    _build_pipeline_semantic_graph,
    _dataset_entry_to_df,
    _descendants,
    _entry_parent_ids,
    _exec_python_merge_transform,
    _exec_python_transform,
    _hard_delete_branch_from_team_state,
    _normalize_readonly_sql,
    _normalize_pipeline_stage,
    _topological_order_for_stale_set,
    _pipeline_studio_branch_ids_for_datasets,
)


def test_dataset_entry_to_df_handles_dict_and_dataframe():
    frame = pd.DataFrame({"a": [1, 2]})
    assert _dataset_entry_to_df({"data": frame}) is frame

    converted = _dataset_entry_to_df({"data": {"a": {0: 1, 1: 2}}})
    assert isinstance(converted, pd.DataFrame)
    assert list(converted.columns) == ["a"]


def test_exec_python_transform_uses_hint_and_returns_dataframe():
    input_df = pd.DataFrame({"x": [1, 2, 3]})
    output_df, function_name = _exec_python_transform(
        code="def transform(df):\n    return df.assign(y=df['x'] * 2)\n",
        df_in=input_df,
        fn_name_hint="transform",
    )
    assert function_name == "transform"
    assert list(output_df.columns) == ["x", "y"]
    assert output_df["y"].tolist() == [2, 4, 6]


def test_pipeline_stage_normalization():
    assert _normalize_pipeline_stage("SQL / Feature Stage") == "sql_feature_stage"
    assert _normalize_pipeline_stage("") == "custom"


def test_branch_helpers_build_transitive_ids():
    datasets = {
        "root": {"parent_id": None},
        "child_a": {"parent_id": "root"},
        "child_b": {"parent_ids": ["root"]},
        "grandchild": {"parent_id": "child_a"},
    }
    children = _build_children_index(datasets)
    assert children["root"] == {"child_a", "child_b"}
    assert _descendants("root", children) == {"child_a", "child_b", "grandchild"}
    assert _pipeline_studio_branch_ids_for_datasets("root", datasets) == {
        "root",
        "child_a",
        "child_b",
        "grandchild",
    }


def test_entry_parent_ids_preserves_existing_parent_ids_order():
    entry = {"parent_id": "p0", "parent_ids": ["p1", "p0", "p2"]}
    assert _entry_parent_ids(entry) == ["p1", "p0", "p2"]


def test_apply_branch_ui_action_handles_all_modes():
    hidden, deleted, label = _apply_branch_ui_action(
        action="soft_delete",
        branch_ids={"a", "b"},
        hidden_ids={"x"},
        deleted_ids={"y"},
    )
    assert hidden == {"x"}
    assert deleted == {"y", "a", "b"}
    assert label == "Soft-deleted"

    hidden, deleted, label = _apply_branch_ui_action(
        action="restore",
        branch_ids={"a", "b"},
        hidden_ids={"x", "a"},
        deleted_ids={"y", "b"},
    )
    assert hidden == {"x"}
    assert deleted == {"y"}
    assert label == "Restored"


def test_hard_delete_branch_from_team_state_keeps_latest_active():
    team_state = {
        "active_dataset_id": "child",
        "datasets": {
            "root": {"created_ts": 1.0},
            "child": {"parent_id": "root", "created_ts": 2.0},
            "other": {"created_ts": 3.0},
        },
    }
    result = _hard_delete_branch_from_team_state(team_state=team_state, root_id="root")
    assert result["ok"] is True
    updated = result["team_state"]
    assert set(updated["datasets"].keys()) == {"other"}
    assert updated["active_dataset_id"] == "other"


def test_build_pipeline_semantic_graph_adds_edges_and_flags():
    graph = _build_pipeline_semantic_graph(
        pipeline_hash="p1",
        node_ids=["a", "b"],
        meta_by_id={"a": {"label": "A"}, "b": {"label": "B"}},
        datasets={"a": {}, "b": {"parent_id": "a"}},
        hidden_ids={"a"},
        deleted_ids={"b"},
    )
    assert graph["pipeline_hash"] == "p1"
    assert graph["edges"] == [{"source": "a", "target": "b"}]
    assert graph["nodes"]["a"]["hidden"] is True
    assert graph["nodes"]["b"]["deleted"] is True


def test_sql_normalizer_and_merge_transform():
    assert _normalize_readonly_sql("SELECT 1;") == "SELECT 1"
    merged = _exec_python_merge_transform(
        code="df = df_0.merge(df_1, on='id', how='inner')",
        parent_dfs=[
            pd.DataFrame({"id": [1, 2], "a": [10, 20]}),
            pd.DataFrame({"id": [2], "b": [99]}),
        ],
    )
    assert merged.to_dict(orient="records") == [{"id": 2, "a": 20, "b": 99}]


def test_topological_order_for_stale_set_uses_parent_dependencies():
    datasets = {
        "root": {"created_ts": 1.0},
        "b": {"parent_id": "root", "created_ts": 2.0},
        "c": {"parent_id": "b", "created_ts": 3.0},
    }
    children = _build_children_index(datasets)
    order = _topological_order_for_stale_set(
        stale_set={"b", "c"},
        parents_by_id={"b": ["root"], "c": ["b"]},
        children_index=children,
        datasets=datasets,
    )
    assert order == ["b", "c"]
