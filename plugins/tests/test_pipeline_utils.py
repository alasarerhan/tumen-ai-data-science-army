from ai_data_science_team.utils.pipeline import build_reproducible_pipeline_script


def test_build_reproducible_pipeline_script_linear_chain():
    datasets = {
        "d1": {
            "label": "raw",
            "stage": "load",
            "provenance": {
                "source_type": "file",
                "source": "sales.csv",
            },
        },
        "d2": {
            "label": "clean",
            "stage": "wrangle",
            "parent_id": "d1",
            "provenance": {
                "transform": {
                    "kind": "python_function",
                    "function_code": "def clean_df(df):\n    return df.dropna()",
                    "function_name": "clean_df",
                }
            },
        },
    }

    script = build_reproducible_pipeline_script(datasets, target_dataset_id="d2")

    assert "Target dataset id: d2" in script
    assert "df = pd.read_csv('sales.csv')" in script
    assert "def clean_df(df):" in script
    assert "df = clean_df(df)" in script
    assert "Final shape" in script


def test_build_reproducible_pipeline_script_merge_branches():
    datasets = {
        "a1": {
            "label": "left_root",
            "stage": "load",
            "provenance": {
                "source_type": "file",
                "source": "left.csv",
            },
        },
        "b1": {
            "label": "right_root",
            "stage": "load",
            "provenance": {
                "source_type": "file",
                "source": "right.csv",
            },
        },
        "m1": {
            "label": "merged",
            "stage": "feature",
            "parent_ids": ["a1", "b1"],
            "provenance": {
                "transform": {
                    "kind": "python_merge",
                    "merge_code": "df = pd.concat([df_0, df_1], axis=0)",
                }
            },
        },
    }

    script = build_reproducible_pipeline_script(datasets, target_dataset_id="m1")

    assert "# --- Branch 1: parent a1 ---" in script
    assert "# --- Branch 2: parent b1 ---" in script
    assert "df_0 = pd.read_csv('left.csv')" in script
    assert "df_1 = pd.read_csv('right.csv')" in script
    assert "df = pd.concat([df_0, df_1], axis=0)" in script
