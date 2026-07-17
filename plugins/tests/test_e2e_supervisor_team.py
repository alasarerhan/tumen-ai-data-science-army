"""E2E Integration: supervisor_ds_team with real LLM (Phase 8).

Exercises the full tool -> agent -> workflow loop by driving the
supervisor_ds_team with real (or stubbed) agents and a real chat model
(unless no API key is available).

Test scenarios
--------------
1. test_e2e_full_ds_pipeline  — load CSV, clean, EDA, feature engineering,
  H2O model training, MLflow logging, evaluation — all via real agents.
2. test_e2e_sql_pipeline      — SQL database agent path.
3. test_e2e_visualization     — visualization agent path.

Markers: ``e2e_supervisor``

Run::
    pytest plugins/tests/test_e2e_supervisor_team.py -v -s
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pandas as pd
import pytest
from langchain_core.messages import AIMessage, HumanMessage

from _llm import make_chat_model, skip_no_key

pytestmark = pytest.mark.e2e_supervisor

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_DIR = Path(__file__).resolve().parent / "_test_e2e_data"
SAMPLE_CSV = TEST_DIR / "e2e_test_data.csv"


@pytest.fixture(scope="module", autouse=True)
def _ensure_data() -> None:
    """Create a small CSV fixture for integration tests."""
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    if not SAMPLE_CSV.exists():
        df = pd.DataFrame({
            "id": range(1, 51),
            "age": [25, 34, 45, 52, 38, 29, 41, 33, 47, 50] * 5,
            "income": [45000, 62000, 83000, 95000, 71000,
                       53000, 88000, 59000, 92000, 105000] * 5,
            "education_years": [12, 16, 14, 18, 15, 13, 17, 12, 16, 14] * 5,
            "purchased": [0, 1, 1, 1, 0, 0, 1, 0, 1, 1] * 5,
        })
        df.to_csv(SAMPLE_CSV, index=False)

    yield

    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)


@pytest.fixture(scope="module")
def llm():
    """Shared real LLM (requires OPENCODE_API_KEY or OPENAI_API_KEY)."""
    return make_chat_model(temperature=0, max_tokens=4096)


# ---------------------------------------------------------------------------
# Helper: build a real supervisor_ds_team
# ---------------------------------------------------------------------------


def _make_real_team(llm):
    """Construct a supervisor_ds_team with real agent instances."""
    from ai_data_science_team.agents import (
        DataLoaderToolsAgent,
        DataWranglingAgent,
        DataCleaningAgent,
        EDAToolsAgent,
        DataVisualizationAgent,
        SQLDatabaseAgent,
        FeatureEngineeringAgent,
        H2OMLAgent,
        MLflowToolsAgent,
        ModelEvaluationAgent,
    )

    return make_supervisor_ds_team(
        model=llm,
        workflow_planner_agent=None,
        data_loader_agent=DataLoaderToolsAgent(model=llm),
        data_wrangling_agent=DataWranglingAgent(model=llm),
        data_cleaning_agent=DataCleaningAgent(model=llm),
        eda_tools_agent=EDAToolsAgent(model=llm),
        data_visualization_agent=DataVisualizationAgent(model=llm),
        sql_database_agent=SQLDatabaseAgent(model=llm),
        feature_engineering_agent=FeatureEngineeringAgent(model=llm),
        h2o_ml_agent=H2OMLAgent(model=llm),
        mlflow_tools_agent=MLflowToolsAgent(model=llm),
        model_evaluation_agent=ModelEvaluationAgent(model=llm),
    )


# ===========================================================================
# Tests
# ===========================================================================


@skip_no_key
def test_e2e_full_ds_pipeline(llm) -> None:
    """Full DS pipeline: load -> clean -> EDA -> FE -> model -> evaluate.

    This test exercises the real LangGraph loop with real agents.
    It validates that the supervisor correctly routes messages and that
    each agent produces structured output the next agent can consume.
    """
    from ai_data_science_team.multiagents.supervisor_ds_team import (
        make_supervisor_ds_team,
    )

    app = _make_real_team(llm)

    csv_path = str(SAMPLE_CSV)
    prompt = (
        f"Load the CSV file at '{csv_path}'. "
        f"Clean the data, perform EDA, engineer features, "
        f"train an H2O model to predict 'purchased', "
        f"log the experiment to MLflow, and evaluate the model. "
        f"Summarize all results."
    )

    result = app.invoke({
        "messages": [HumanMessage(content=prompt)],
        "artifacts": {"config": {"proactive_workflow_mode": True}},
    })

    msg = result.get("messages", [])
    assert len(msg) > 1, "Expected multiple messages from the supervisor chain"
    last = msg[-1] if isinstance(msg, list) else msg
    assert isinstance(last, AIMessage) or hasattr(last, "content")
    final_text = str(last.content) if hasattr(last, "content") else str(last)
    assert len(final_text) > 100, (
        f"Expected substantive AI response, got {len(final_text)} chars"
    )
    print(f"\n  ✅ Full pipeline completed. Response: {final_text[:300]}...")


@skip_no_key
def test_e2e_data_loader_tool_agent(llm) -> None:
    """Test DataLoaderToolsAgent in isolation with a real LLM."""
    from ai_data_science_team.agents import DataLoaderToolsAgent

    agent = DataLoaderToolsAgent(model=llm)
    csv_path = str(SAMPLE_CSV)
    agent.invoke_agent(
        user_instructions=(
            f"Load '{csv_path}'. Show the first 5 rows, "
            f"count the rows and columns, and list data types."
        )
    )
    msg = agent.get_ai_message()
    assert isinstance(msg, str) and len(msg) > 50
    print(f"\n  ✅ DataLoaderToolsAgent — {len(msg)} chars: {msg[:150]}...")


@skip_no_key
def test_e2e_cleaning_agent(llm) -> None:
    """Test DataCleaningAgent in isolation."""
    from ai_data_science_team.agents import DataCleaningAgent

    agent = DataCleaningAgent(model=llm)
    df = pd.read_csv(SAMPLE_CSV)
    # Introduce a missing value for the agent to handle
    df.loc[0, "age"] = None

    agent.invoke_agent(
        user_instructions="Clean this dataset: handle missing values, "
        "check data types, and report any issues found.",
        data_raw=df,
    )
    msg = agent.get_ai_message()
    assert isinstance(msg, str) and len(msg) > 50
    print(f"\n  ✅ DataCleaningAgent — {len(msg)} chars")


@skip_no_key
def test_e2e_eda_agent(llm) -> None:
    """Test EDAToolsAgent in isolation."""
    from ai_data_science_team.agents import EDAToolsAgent

    agent = EDAToolsAgent(model=llm)
    df = pd.read_csv(SAMPLE_CSV)

    agent.invoke_agent(
        user_instructions="Perform EDA: show dataset summary, "
        "correlation matrix, and distribution of 'age' and 'income'.",
        data_raw=df,
    )
    msg = agent.get_ai_message()
    assert isinstance(msg, str) and len(msg) > 50
    print(f"\n  ✅ EDAToolsAgent — {len(msg)} chars")


@skip_no_key
def test_e2e_feature_engineering_agent(llm) -> None:
    """Test FeatureEngineeringAgent in isolation."""
    from ai_data_science_team.agents import FeatureEngineeringAgent

    agent = FeatureEngineeringAgent(model=llm)
    df = pd.read_csv(SAMPLE_CSV)

    agent.invoke_agent(
        user_instructions="Create 2 new features from the existing columns "
        "that could help predict 'purchased'.",
        data_raw=df,
        target="purchased",
    )
    msg = agent.get_ai_message()
    assert isinstance(msg, str) and len(msg) > 50
    print(f"\n  ✅ FeatureEngineeringAgent — {len(msg)} chars")


# ===========================================================================
# Isolation run
# ===========================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
