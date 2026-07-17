"""
End-to-end Data Science Pipeline Test (Agentic).

Tests the full ML workflow using real LLM agents:
  1. Load sample data (Iris dataset from sklearn)
  2. Load & explore data via DataLoaderToolsAgent
  3. Train ML models using sklearn directly (orchestrated by LLM)
  4. Interpret results via LLM

Run:  uv run pytest plugins/tests/test_end2end_ds_pipeline.py -v -s
"""
from __future__ import annotations

import os
import json
from pathlib import Path

import pytest
import pandas as pd

from _llm import make_chat_model, skip_no_key

pytestmark = pytest.mark.e2e_ds

# Temp directory for sample data and outputs
DATA_DIR = Path(__file__).resolve().parent / "_test_data"
DATA_DIR.mkdir(exist_ok=True)

SAMPLE_CSV = DATA_DIR / "iris_dataset.csv"


def _ensure_sample_data():
    """Create Iris CSV."""
    if SAMPLE_CSV.exists():
        return
    try:
        from sklearn.datasets import load_iris
    except ImportError:
        pytest.skip("scikit-learn not installed")

    iris = load_iris()
    df = pd.DataFrame(iris.data, columns=iris.feature_names)
    df["species"] = iris.target_names[iris.target]
    df.to_csv(SAMPLE_CSV, index=False)
    print(f"\n  [setup] Created {SAMPLE_CSV} ({len(df)} rows, {len(df.columns)} cols)")


def _cleanup():
    import shutil
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)


@pytest.fixture(scope="module")
def llm():
    """Shared LLM."""
    return make_chat_model(temperature=0, max_tokens=2000)


# ---------------------------------------------------------------------------
# 1. Data Loading & Exploration (via DataLoaderToolsAgent)
# ---------------------------------------------------------------------------

@skip_no_key
def test_01_data_loading(llm):
    """Load and preview the Iris CSV."""
    _ensure_sample_data()

    from ai_data_science_team.agents import DataLoaderToolsAgent
    agent = DataLoaderToolsAgent(model=llm)
    agent.invoke_agent(
        user_instructions=(
            f"Load the CSV file at '{SAMPLE_CSV}'. "
            f"Read it and show me: the number of rows/columns, "
            f"all column names with their data types, "
            f"and the first 5 rows."
        )
    )
    msg = agent.get_ai_message()
    assert isinstance(msg, str) and len(msg) > 50
    print(f"\n  ✅ Data Loading — {len(msg)} chars")
    print(f"  {msg[:200]}...")


# ---------------------------------------------------------------------------
# 2. LLM-Generated ML Pipeline (agent orchestrates sklearn code)
# ---------------------------------------------------------------------------

@skip_no_key
def test_02_llm_orchestrated_ml(llm):
    """LLM writes & explains a complete ML pipeline: load → train → evaluate.

    The LLM generates sklearn code, we execute it, then LLM interprets results.
    """
    _ensure_sample_data()
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, classification_report

    # --- Step A: LLM loads & analyzes data via agent ---
    print("\n  ── Step A: Loading & Profiling ──")
    from ai_data_science_team.agents import DataLoaderToolsAgent
    loader = DataLoaderToolsAgent(model=llm)
    loader.invoke_agent(
        user_instructions=(
            f"Load CSV at '{SAMPLE_CSV}' and compute: "
            f"class distribution of 'species', "
            f"basic stats (mean/min/max) of each numeric column, "
            f"and check for any missing values."
        )
    )
    profile_msg = loader.get_ai_message()
    print(f"  Profile: {profile_msg[:200]}...")

    # --- Step B: Train sklearn model directly ---
    print("\n  ── Step B: Training Model ──")
    df = pd.read_csv(SAMPLE_CSV)
    X = df.drop(columns=["species"])
    y = df["species"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    report = classification_report(y_test, y_pred, output_dict=True)

    print(f"  Accuracy: {acc:.2%}")
    print(f"  Model: RandomForestClassifier(n=100)")

    # Feature importance
    feat_imp = sorted(
        zip(X.columns, model.feature_importances_),
        key=lambda x: x[1], reverse=True
    )
    print(f"  Top features: {feat_imp[:3]}")

    # Save results for LLM interpretation
    results = {
        "accuracy": round(acc, 4),
        "model": "RandomForestClassifier(n_estimators=100)",
        "n_train": len(X_train),
        "n_test": len(X_test),
        "feature_importances": [
            {"feature": f, "importance": round(i, 4)} for f, i in feat_imp
        ],
        "classification_report": {
            label: (
                {k: round(v, 4) if isinstance(v, float) else v
                 for k, v in metrics.items()}
                if isinstance(metrics, dict) else round(metrics, 4)
            )
            for label, metrics in report.items()
        }
    }

    # --- Step C: LLM interprets results ---
    print("\n  ── Step C: Interpreting Results ──")

    from langchain_openai import ChatOpenAI
    interpreter = ChatOpenAI(
        model="deepseek-v4-flash",
        api_key=os.getenv("OPENCODE_API_KEY") or os.getenv("OPENAI_API_KEY"),
        base_url="https://opencode.ai/zen/v1",
        temperature=0,
        max_tokens=1000,
    )

    interpretation = interpreter.invoke([
        {"role": "system", "content": "You are a data science interpreter. "
         "Explain ML results concisely in Turkish."},
        {"role": "user", "content": f"Şu ML sonuçlarını yorumla:\n{json.dumps(results, indent=2)}"}
    ])
    print(f"  LLM Yorumu:\n  {interpretation.content[:500]}")

    assert acc > 0.5, f"Model accuracy too low: {acc}"
    print(f"\n  ✅ Full pipeline completed. Accuracy: {acc:.2%}")


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def teardown_module():
    _cleanup()
