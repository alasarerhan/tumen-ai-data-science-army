from __future__ import annotations

from typing import Any

from .merge_support import parse_list_value


def execute_merge_plan(dfs: list[Any], merge_cfg: dict[str, Any], last_human: str):
    import pandas as pd  # noqa: E402, F401

    op = str(merge_cfg.get("operation") or "join").strip().lower()
    if any(word in last_human.lower() for word in ("concat", "append", "union")):
        op = "concat"
    if op not in ("join", "concat"):
        op = "join"

    merge_code_lines: list[str] = ["# Auto-generated merge step"]
    merge_meta: dict[str, Any] = {"operation": op}

    if op == "concat":
        axis = merge_cfg.get("axis", 0)
        try:
            axis = int(axis)
        except Exception:
            axis = 0
        ignore_index = bool(merge_cfg.get("ignore_index", True))
        merged_df = pd.concat(dfs, axis=axis, ignore_index=(ignore_index if axis == 0 else False))
        merge_meta.update({"axis": axis, "ignore_index": ignore_index})
        merge_code_lines.append(
            f"df = pd.concat([{', '.join([f'df_{i}' for i in range(len(dfs))])}], axis={axis}, ignore_index={ignore_index if axis == 0 else False})"
        )
        return {
            "ok": True,
            "operation": op,
            "merged_df": merged_df,
            "merge_meta": merge_meta,
            "merge_code": "\n".join(merge_code_lines).strip() + "\n",
        }

    how = str(merge_cfg.get("how") or "inner").strip().lower()
    if how not in ("inner", "left", "right", "outer"):
        how = "inner"
    on_cols = parse_list_value(merge_cfg.get("on"))
    left_on = parse_list_value(merge_cfg.get("left_on"))
    right_on = parse_list_value(merge_cfg.get("right_on"))
    suffixes_raw = str(merge_cfg.get("suffixes") or "_x,_y")
    suffixes_parts = [part.strip() for part in suffixes_raw.split(",") if part.strip()]
    suffixes = (suffixes_parts[0], suffixes_parts[1]) if len(suffixes_parts) >= 2 else ("_x", "_y")

    if not on_cols and not (left_on and right_on):
        common = set(dfs[0].columns)
        for df in dfs[1:]:
            common = common.intersection(set(df.columns))
        if common:
            preferred = sorted(
                list(common),
                key=lambda column: (
                    0 if "id" in str(column).lower() else 1,
                    str(column).lower(),
                ),
            )
            on_cols = [preferred[0]]

    if not on_cols and not (left_on and right_on):
        return {
            "ok": False,
            "error_message": (
                "I couldn't infer join keys for the selected datasets. "
                "Specify join keys in your request (e.g., `join on customerID`), "
                "or configure them in Pipeline Studio."
            ),
        }

    merged_df = dfs[0]
    merge_code_lines.append("df = df_0")
    for index in range(1, len(dfs)):
        if left_on and right_on:
            merged_df = merged_df.merge(
                dfs[index],
                how=how,
                left_on=left_on,
                right_on=right_on,
                suffixes=suffixes,
            )
            merge_code_lines.append(
                f"df = df.merge(df_{index}, how={how!r}, left_on={left_on!r}, right_on={right_on!r}, suffixes={suffixes!r})"
            )
        else:
            merged_df = merged_df.merge(
                dfs[index],
                how=how,
                on=on_cols,
                suffixes=suffixes,
            )
            merge_code_lines.append(
                f"df = df.merge(df_{index}, how={how!r}, on={on_cols!r}, suffixes={suffixes!r})"
            )

    merge_meta.update(
        {
            "how": how,
            "on": on_cols,
            "left_on": left_on,
            "right_on": right_on,
            "suffixes": suffixes,
        }
    )
    return {
        "ok": True,
        "operation": op,
        "merged_df": merged_df,
        "merge_meta": merge_meta,
        "merge_code": "\n".join(merge_code_lines).strip() + "\n",
    }
