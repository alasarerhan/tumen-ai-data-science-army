from __future__ import annotations

from ai_data_science_team.utils.sandbox import run_code_sandboxed_subprocess


def test_sandbox_runner_executes_dataframe_function() -> None:
    code = """
def transform(df):
    return {"rows": len(df), "total": int(df["value"].sum())}
"""

    result, error = run_code_sandboxed_subprocess(
        code_snippet=code,
        function_name="transform",
        data={"value": [1, 2, 3]},
        timeout=10,
    )

    assert error is None
    assert result == {"rows": 3, "total": 6}


def test_sandbox_runner_blocks_dangerous_imports() -> None:
    code = """
import socket

def transform(df):
    return {"rows": len(df)}
"""

    result, error = run_code_sandboxed_subprocess(
        code_snippet=code,
        function_name="transform",
        data={"value": [1]},
        timeout=10,
    )

    assert result is None
    assert error == "Import of 'socket' is blocked."
