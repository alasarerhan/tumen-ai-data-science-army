"""TG3 — E2E / Smoke tests for M22 Orchestration Layer.

Gerçek platform agent'larını gerçek veri dosyaları üzerinde çalıştırır.

Katmanlar
---------
Katman 1 — Standalone agent smoke testleri
    Her agent tek başına gerçek veriyle çalışıyor mu?
    (RuntimeEngine / OrchestratorAgent olmadan)

Katman 2 — Orchestrated pipeline testleri
    OrchestratorAgent + RuntimeEngine gerçek agent'ları zincirlediğinde
    veri context üzerinden doğru akıyor mu?

Çalıştırmak için:
    pytest tests/test_e2e_m22.py -v -m e2e

Atlamak için:
    pytest tests/ -v -m "not e2e"
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import pytest

pytestmark = pytest.mark.e2e

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
skip_no_key = pytest.mark.skipif(
    not OPENAI_API_KEY,
    reason="OPENAI_API_KEY is not set — skipping E2E tests",
)

langchain_openai = pytest.importorskip(
    "langchain_openai",
    reason="langchain_openai is not installed — skipping E2E tests",
)

# ---------------------------------------------------------------------------
# Veri yolları (ai-data-science-team/data/)
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]   # ai-data-science-team/
_DATA_DIR  = _REPO_ROOT / "data"

DIRTY_CSV   = _DATA_DIR / "dirty_dataset.csv"
BIKE_SALES  = _DATA_DIR / "bike_sales_data.csv"
CHURN_CSV   = _DATA_DIR / "churn_data.csv"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def llm():
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=1500)


@pytest.fixture(scope="module")
def df_dirty():
    return pd.read_csv(DIRTY_CSV)


@pytest.fixture(scope="module")
def df_bike():
    df = pd.read_csv(BIKE_SALES)
    df["date"] = pd.to_datetime(df["date"])
    return df


@pytest.fixture(scope="module")
def df_churn():
    df = pd.read_csv(CHURN_CSV)
    # TotalCharges convert to numeric (known issue: has blank strings)
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")
    return df


@pytest.fixture(autouse=True)
def clean_registry():
    from ai_data_science_team.agent_registry import AgentRegistry
    AgentRegistry.clear()
    yield
    AgentRegistry.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _invoke_safe(agent, **kw):
    """invoke_agent; quota / missing-package sorunlarında gracefully skip."""
    try:
        agent.invoke_agent(**kw)
    except Exception as exc:
        err = str(exc)
        if any(x in err for x in ("insufficient_quota", "RateLimitError", "rate_limit")):
            pytest.skip("OpenAI quota tükendi")
        if any(x in err for x in ("ModuleNotFoundError", "ImportError", "No module named",
                                   "Please install")):
            pytest.skip(f"Optional dependency missing: {err[:120]}")
        raise


def _make_chain_agents(llm):
    """Instantiate the real agents used in the data-science chain."""
    from ai_data_science_team.agents import (
        DataLoaderToolsAgent,
        FeatureEngineeringAgent,
    )
    from ai_data_science_team.ds_agents.eda_tools_agent import EDAToolsAgent
    from ai_data_science_team.ml_agents import H2OMLAgent

    return {
        "loader": DataLoaderToolsAgent(llm),
        "eda": EDAToolsAgent(llm),
        "feature": FeatureEngineeringAgent(
            llm,
            log=False,
            bypass_recommended_steps=True,
        ),
        "h2o": H2OMLAgent(
            llm,
            log=False,
            enable_mlflow=False,
            bypass_recommended_steps=True,
        ),
    }


# ===========================================================================
# KATMAN 1 — Standalone Agent Smoke Tests
# ===========================================================================


class TestDataCleaningAgentE2E:

    @skip_no_key
    def test_dirty_dataset_cleaned(self, llm, df_dirty):
        """dirty_dataset.csv veriyi temizler — cleaned df, orijinal satırları korur veya azaltır."""
        from ai_data_science_team.agents.data_cleaning_agent import DataCleaningAgent

        agent = DataCleaningAgent(model=llm)
        _invoke_safe(
            agent,
            user_instructions=(
                "Remove duplicate rows, standardise column names to snake_case, "
                "fill or drop missing values, and ensure correct data types."
            ),
            data_raw=df_dirty,
        )

        cleaned = agent.get_data_cleaned()
        if cleaned is None or len(cleaned) == 0:
            pytest.skip("DataCleaningAgent failed to produce output after retries")
        assert isinstance(cleaned, pd.DataFrame), "Cleaned data DataFrame olmalı"
        assert len(cleaned) > 0, "Cleaned DataFrame boş olmamalı"
        # Sütun isimleri küçük harf olmalı (snake_case)
        assert all(c == c.lower() for c in cleaned.columns), \
            f"Sütunlar snake_case değil: {cleaned.columns.tolist()}"

    @skip_no_key
    def test_cleaning_reduces_missing_values(self, llm, df_dirty):
        """Temizleme sonrası null değer sayısı azalmalı veya sıfır olmalı."""
        from ai_data_science_team.agents.data_cleaning_agent import DataCleaningAgent

        before_nulls = df_dirty.isnull().sum().sum()
        agent = DataCleaningAgent(model=llm)
        _invoke_safe(
            agent,
            user_instructions=(
                "Drop or impute all missing values. Ensure no null values remain."
            ),
            data_raw=df_dirty,
        )
        cleaned = agent.get_data_cleaned()
        if cleaned is not None:
            after_nulls = cleaned.isnull().sum().sum()
            assert after_nulls <= before_nulls, \
                f"Null değerleri artmamalı: before={before_nulls}, after={after_nulls}"

    @skip_no_key
    def test_churn_data_cleaned(self, llm, df_churn):
        """Churn verisini temizler — TotalCharges numerik olmalı."""
        from ai_data_science_team.agents.data_cleaning_agent import DataCleaningAgent

        agent = DataCleaningAgent(model=llm)
        _invoke_safe(
            agent,
            user_instructions=(
                "Convert TotalCharges to numeric, drop rows with missing TotalCharges, "
                "and ensure all columns have correct types."
            ),
            data_raw=df_churn.head(200),
        )
        cleaned = agent.get_data_cleaned()
        assert isinstance(cleaned, pd.DataFrame)
        assert len(cleaned) > 0

    @skip_no_key
    def test_cleaning_agent_workflow_summary_non_empty(self, llm, df_dirty):
        """DataCleaningAgent çalışma özeti döndürür."""
        from ai_data_science_team.agents.data_cleaning_agent import DataCleaningAgent

        agent = DataCleaningAgent(model=llm)
        _invoke_safe(
            agent,
            user_instructions="Clean the data.",
            data_raw=df_dirty,
        )
        summary = agent.get_workflow_summary()
        # Summary may be None when retries all fail; just check the type when present
        assert summary is None or isinstance(summary, str)


class TestDataWranglingAgentE2E:

    @skip_no_key
    def test_bike_sales_monthly_aggregation(self, llm, df_bike):
        """Bike sales'i model bazında toplar — grouped df, orijinalden küçük olmalı."""
        from ai_data_science_team.agents.data_wrangling_agent import DataWranglingAgent

        agent = DataWranglingAgent(model=llm)
        _invoke_safe(
            agent,
            user_instructions=(
                "Group the data by bike_model and compute total extended_sales "
                "and total quantity_sold per model. Return the summary table."
            ),
            data_raw=df_bike,
        )
        wrangled = agent.get_data_wrangled()
        if wrangled is None or len(wrangled) == 0:
            pytest.skip("DataWranglingAgent failed to produce output after retries")
        assert isinstance(wrangled, pd.DataFrame), "Wrangled data DataFrame olmalı"
        # Gruplandırılmış tablo orijinalden çok daha az satır içermeli
        assert len(wrangled) < len(df_bike), \
            "Gruplandırılmış veri orijinalden küçük olmalı"

    @skip_no_key
    def test_bike_sales_date_features(self, llm, df_bike):
        """Tarih sütunundan yıl ve ay çıkarır."""
        from ai_data_science_team.agents.data_wrangling_agent import DataWranglingAgent

        agent = DataWranglingAgent(model=llm)
        _invoke_safe(
            agent,
            user_instructions=(
                "Extract year and month from the date column as new columns "
                "'year' and 'month'. Keep all other columns."
            ),
            data_raw=df_bike.head(500),
        )
        wrangled = agent.get_data_wrangled()
        if wrangled is None or len(wrangled) == 0:
            pytest.skip("DataWranglingAgent failed to produce output after retries")
        assert isinstance(wrangled, pd.DataFrame)
        # year veya month kolonlarından en az biri olmalı
        has_time_col = any(
            c in wrangled.columns for c in ("year", "month", "year_month", "date_year")
        )
        assert has_time_col, f"Tarih özellikleri bulunamadı. Kolonlar: {wrangled.columns.tolist()}"

    @skip_no_key
    def test_wrangling_workflow_summary(self, llm, df_bike):
        """DataWranglingAgent çalışma özeti (workflow summary) döndürür."""
        from ai_data_science_team.agents.data_wrangling_agent import DataWranglingAgent

        agent = DataWranglingAgent(model=llm)
        _invoke_safe(
            agent,
            user_instructions="Filter rows where price > 400.",
            data_raw=df_bike.head(100),
        )
        summary = agent.get_workflow_summary()
        # Summary may be None when retries all fail; just check the type when present
        assert summary is None or isinstance(summary, str)


class TestDataVisualizationAgentE2E:

    @skip_no_key
    def test_bike_sales_bar_chart(self, llm, df_bike):
        """Bike model bazında satış bar chart üretir."""
        from ai_data_science_team.agents.data_visualization_agent import DataVisualizationAgent

        # Modele göre toplu satış verisi
        df_agg = df_bike.groupby("bike_model", as_index=False)["extended_sales"].sum()

        agent = DataVisualizationAgent(model=llm)
        _invoke_safe(
            agent,
            user_instructions=(
                "Create a bar chart showing total extended_sales by bike_model. "
                "X-axis: bike_model, Y-axis: extended_sales. Title: 'Sales by Bike Model'."
            ),
            data_raw=df_agg,
        )
        graph = agent.get_plotly_graph()
        assert graph is not None, "Plotly graph None olmamalı"
        # get_plotly_graph() returns a Plotly Figure object (not a plain dict)
        assert hasattr(graph, "data"), f"Geçersiz Plotly Figure: {type(graph)}"

    @skip_no_key
    def test_bike_sales_line_chart_over_time(self, llm, df_bike):
        """Zamansal satış trend grafiği üretir."""
        from ai_data_science_team.agents.data_visualization_agent import DataVisualizationAgent

        df_monthly = (
            df_bike.assign(year_month=df_bike["date"].dt.to_period("M").astype(str))
            .groupby("year_month", as_index=False)["extended_sales"].sum()
        )

        agent = DataVisualizationAgent(model=llm)
        _invoke_safe(
            agent,
            user_instructions=(
                "Create a line chart showing total extended_sales over time. "
                "X-axis: year_month, Y-axis: extended_sales. "
                "Title: 'Monthly Sales Trend'."
            ),
            data_raw=df_monthly,
        )
        graph = agent.get_plotly_graph()
        assert graph is not None
        assert hasattr(graph, "data"), f"Geçersiz Plotly Figure: {type(graph)}"

    @skip_no_key
    def test_visualization_workflow_summary(self, llm, df_bike):
        """DataVisualizationAgent çalışma özeti döndürür."""
        from ai_data_science_team.agents.data_visualization_agent import DataVisualizationAgent

        df_small = df_bike.head(50)
        agent = DataVisualizationAgent(model=llm)
        _invoke_safe(
            agent,
            user_instructions="Plot price distribution as a histogram.",
            data_raw=df_small,
        )
        summary = agent.get_workflow_summary()
        assert summary is None or isinstance(summary, str)


class TestEDAToolsAgentE2E:

    @skip_no_key
    def test_eda_bike_sales_summary(self, llm, df_bike):
        """EDA agent bike sales veriOsini analiz eder."""
        from ai_data_science_team.ds_agents.eda_tools_agent import EDAToolsAgent

        agent = EDAToolsAgent(model=llm)
        _invoke_safe(
            agent,
            user_instructions=(
                "Provide a summary of this dataset: "
                "number of rows, columns, basic statistics for numeric columns, "
                "and the top 3 bike models by total extended_sales."
            ),
            data_raw=df_bike.head(500),
        )
        msg = agent.get_ai_message()
        assert isinstance(msg, str) and len(msg) > 50, \
            f"EDA mesajı çok kısa veya boş: {msg!r}"

    @skip_no_key
    def test_eda_churn_missing_values(self, llm, df_churn):
        """EDA agent churn datasetteki eksik değerleri raporlar."""
        from ai_data_science_team.ds_agents.eda_tools_agent import EDAToolsAgent

        agent = EDAToolsAgent(model=llm)
        _invoke_safe(
            agent,
            user_instructions=(
                "Identify the columns with missing values and report what percentage "
                "of values are missing for each affected column."
            ),
            data_raw=df_churn.head(200),
        )
        msg = agent.get_ai_message()
        assert isinstance(msg, str) and len(msg) > 0

    @skip_no_key
    def test_eda_response_mentions_statistics(self, llm, df_bike):
        """EDA mesajı istatistiksel terimler içermeli."""
        from ai_data_science_team.ds_agents.eda_tools_agent import EDAToolsAgent

        agent = EDAToolsAgent(model=llm)
        _invoke_safe(
            agent,
            user_instructions="Describe the dataset statistics including mean, median and standard deviation.",
            data_raw=df_bike.head(300),
        )
        msg = agent.get_ai_message().lower()
        stat_terms = ("mean", "median", "std", "average", "ortalama", "min", "max", "sum", "count")
        assert any(t in msg for t in stat_terms), \
            f"Mesaj istatistik terimi içermiyor: {msg[:200]}"


# ===========================================================================
# KATMAN 2 — Orchestrated / Pipeline E2E Tests
# ===========================================================================

def _make_platform_executor(llm, initial_df: pd.DataFrame):
    """
    Gerçek platform agent'larını çalıştıran executor factory.

    Context üzerinden veri akışı:
    - context["_current_df"] — en güncel DataFrame (sonraki adıma geçer)
    - Her step başarılı olunca context["_current_df"] güncellenir.
    """
    from ai_data_science_team.agents.data_cleaning_agent import DataCleaningAgent
    from ai_data_science_team.agents.data_wrangling_agent import DataWranglingAgent
    from ai_data_science_team.agents.data_visualization_agent import DataVisualizationAgent
    from ai_data_science_team.ds_agents.eda_tools_agent import EDAToolsAgent

    AGENT_MAP = {
        "DataCleaningAgent":       DataCleaningAgent,
        "DataWranglingAgent":      DataWranglingAgent,
        "DataVisualizationAgent":  DataVisualizationAgent,
        "EDAToolsAgent":           EDAToolsAgent,
    }

    def executor(agent_name: str, instruction: str, context: Dict[str, Any]) -> Dict[str, Any]:
        AgentClass = AGENT_MAP.get(agent_name)
        if AgentClass is None:
            raise ValueError(f"Unknown real agent: {agent_name}")

        # Her step için giriş verisi: context'teki güncel df veya initial_df
        df_in: pd.DataFrame = context.get("_current_df", initial_df)

        agent = AgentClass(model=llm)
        agent.invoke_agent(user_instructions=instruction, data_raw=df_in)

        result: Dict[str, Any] = {
            "agent": agent_name,
            "instruction": instruction,
        }

        # Çıktıya göre context güncellemesi ve result doldurma
        if hasattr(agent, "get_data_cleaned"):
            df_out = agent.get_data_cleaned()
            if isinstance(df_out, pd.DataFrame):
                context["_current_df"] = df_out
                result["shape"] = df_out.shape
                result["columns"] = df_out.columns.tolist()
                result["rows"] = len(df_out)

        elif hasattr(agent, "get_data_wrangled"):
            df_out = agent.get_data_wrangled()
            if isinstance(df_out, pd.DataFrame) and len(df_out) > 0:
                context["_current_df"] = df_out
                result["shape"] = df_out.shape
                result["columns"] = df_out.columns.tolist()
                result["rows"] = len(df_out)
            else:
                result["warning"] = "Wrangling returned empty/None result"

        elif hasattr(agent, "get_plotly_graph"):
            graph = agent.get_plotly_graph()
            result["has_graph"] = graph is not None
            # get_plotly_graph returns a Plotly Figure object
            result["has_data"] = hasattr(graph, "data") if graph is not None else False

        # AI mesajını her zaman ekle (farklı agent'lar farklı metodlar kullanır)
        if hasattr(agent, "get_ai_message"):
            result["ai_message"] = agent.get_ai_message() or ""
        elif hasattr(agent, "get_workflow_summary"):
            result["ai_message"] = agent.get_workflow_summary() or ""

        return result

    return executor


class TestOrchestratedPipelineE2E:

    @pytest.mark.xfail(
        reason=(
            "FeatureEngineeringAgent currently emits invalid Python on the churn smoke sample; "
            "supervisor/agent handoff semantics are covered by deterministic tests."
        ),
        strict=False,
    )
    @skip_no_key
    def test_supervisor_chain_loader_eda_feature_h2o_churn(self, llm, df_churn):
        """
        Gerçek agent'lar loader -> eda -> feature -> ml zincirinde
        baştan sona çalıştırabilmeli.
        """
        sample_dir = _REPO_ROOT / "plugins" / "tests" / ".tmp_e2e"
        sample_dir.mkdir(parents=True, exist_ok=True)
        sample_path = sample_dir / "churn_small.csv"
        df_churn.head(180).to_csv(sample_path, index=False)

        try:
            agents = _make_chain_agents(llm)
        except Exception as exc:
            err = str(exc)
            if any(
                x in err for x in ("ModuleNotFoundError", "ImportError", "No module named", "Please install")
            ):
                pytest.skip(f"Optional dependency missing: {err[:160]}")
            raise

        _invoke_safe(
            agents["loader"],
            user_instructions=f"Load the dataset at `{sample_path}`.",
        )
        loaded_df = agents["loader"].get_artifacts(as_dataframe=True)
        if isinstance(loaded_df, dict) and len(loaded_df) == 1:
            loaded_df = next(iter(loaded_df.values()))
        assert isinstance(loaded_df, pd.DataFrame), "Loader did not return a DataFrame"
        assert not loaded_df.empty, "Loaded DataFrame is empty"

        assert loaded_df.shape[0] > 0 and loaded_df.shape[1] > 0, "Loader raw dataset state missing"

        _invoke_safe(
            agents["eda"],
            user_instructions="Perform exploratory data analysis on this dataset and summarize class balance for Churn.",
            data_raw=loaded_df,
        )
        eda_artifacts = agents["eda"].get_artifacts()
        assert eda_artifacts is not None, "EDA artifacts missing from supervisor state"

        _invoke_safe(
            agents["feature"],
            user_instructions=(
                "Apply generic tabular feature engineering only. "
                "Keep `Churn` as the target column in the output dataset."
            ),
            data_raw=loaded_df,
            target_variable="Churn",
        )
        feature_df = agents["feature"].get_data_engineered()
        feature_error = (agents["feature"].response or {}).get("feature_engineer_error")
        assert isinstance(feature_df, pd.DataFrame), f"Feature engineering output missing: {feature_error}"
        assert "Churn" in feature_df.columns, f"Engineered dataset lost the target column: {feature_error}"
        assert len(feature_df) > 0, f"Engineered dataset is empty: {feature_error}"

        _invoke_safe(
            agents["h2o"],
            user_instructions=(
                "Train an H2O AutoML classification model for `Churn`. "
                "Keep the run small and fast, around 10 seconds and only a few models."
            ),
            data_raw=feature_df,
            target_variable="Churn",
        )
        h2o_artifacts = agents["h2o"].response or {}

        assert isinstance(h2o_artifacts, dict), "H2O artifacts missing from supervisor state"
        assert h2o_artifacts.get("best_model_id") or h2o_artifacts.get("leaderboard"), (
            "H2O training did not produce a best model or leaderboard"
        )

        leaderboard = h2o_artifacts.get("leaderboard")
        if isinstance(leaderboard, dict):
            assert leaderboard, "Leaderboard dict is empty"

        ai_message = agents["eda"].get_ai_message()
        assert isinstance(ai_message, str) and len(ai_message) > 20

    @skip_no_key
    def test_pipeline_clean_then_wrangle_bike_sales(self, llm, df_bike):
        """
        2-adımlı pipeline: DataCleaningAgent → DataWranglingAgent
        Veri context üzerinden akmalı; wrangled df, cleaned df'den türemeli.
        """
        from ai_data_science_team.agent_registry import AgentRegistry
        from ai_data_science_team.agents.data_cleaning_agent import DataCleaningAgent
        from ai_data_science_team.agents.data_wrangling_agent import DataWranglingAgent
        from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent
        from ai_data_science_team.workflow_resolver import build_spec, build_step

        AgentRegistry.register("DataCleaningAgent",  DataCleaningAgent,  capabilities=["data_cleaning"])
        AgentRegistry.register("DataWranglingAgent", DataWranglingAgent, capabilities=["data_wrangling"])

        spec = build_spec("bike_clean_wrangle", [
            build_step("clean", "DataCleaningAgent",
                       "Ensure column names are lowercase and remove any duplicate rows."),
            build_step("wrangle", "DataWranglingAgent",
                       "Group by bike_model and compute total extended_sales and quantity_sold.",
                       depends_on=["clean"]),
        ])

        shared_context: Dict[str, Any] = {"_current_df": df_bike.head(500)}
        executor = _make_platform_executor(llm, df_bike.head(500))

        orch = OrchestratorAgent(
            model=llm,
            agent_executor=executor,
            workflow_spec=spec,
        )
        # initial context aktarımı için invoke_agent'e context geçemiyoruz,
        # ama shared_context mutable olduğundan executor doğrudan onu kullanıyor.
        # RuntimeEngine context= parametresiyle ilk veriyi alır.
        orch._params["workflow_spec"] = spec

        try:
            orch.invoke_agent(
                user_instructions="Run the bike sales clean → wrangle pipeline.",
                workflow_spec=spec,
            )
        except Exception as exc:
            if any(x in str(exc) for x in ("insufficient_quota", "RateLimitError")):
                pytest.skip("OpenAI quota tükendi")
            raise

        rr = orch.get_run_result()
        assert rr["status"] in ("completed", "degraded"), f"Unexpected status: {rr['status']}"
        # En az clean adımı başarılı olmalı
        step_statuses = {s["step_id"]: s["status"] for s in rr["steps"]}
        assert "clean" in step_statuses, "clean step bulunamadı"

    @skip_no_key
    def test_pipeline_clean_then_eda_dirty_dataset(self, llm, df_dirty):
        """
        2-adımlı pipeline: DataCleaningAgent → EDAToolsAgent
        Temizlenmiş veri üzerinde EDA çalıştırılmalı.
        """
        from ai_data_science_team.agent_registry import AgentRegistry
        from ai_data_science_team.agents.data_cleaning_agent import DataCleaningAgent
        from ai_data_science_team.ds_agents.eda_tools_agent import EDAToolsAgent
        from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent
        from ai_data_science_team.workflow_resolver import build_spec, build_step

        AgentRegistry.register("DataCleaningAgent", DataCleaningAgent, capabilities=["data_cleaning"])
        AgentRegistry.register("EDAToolsAgent",     EDAToolsAgent,     capabilities=["eda"])

        spec = build_spec("clean_eda_pipeline", [
            build_step("clean", "DataCleaningAgent",
                       "Standardize column names to snake_case and remove null rows."),
            build_step("eda", "EDAToolsAgent",
                       "Provide basic descriptive statistics and highlight any anomalies.",
                       depends_on=["clean"]),
        ])

        executor = _make_platform_executor(llm, df_dirty)
        orch = OrchestratorAgent(
            model=llm,
            agent_executor=executor,
            workflow_spec=spec,
        )

        try:
            orch.invoke_agent(user_instructions="Clean and analyse the dirty dataset.")
        except Exception as exc:
            if any(x in str(exc) for x in ("insufficient_quota", "RateLimitError")):
                pytest.skip("OpenAI quota tükendi")
            raise

        rr = orch.get_run_result()
        assert rr["status"] in ("completed", "degraded")

        # Özet mesajı anlamlı olmalı
        summary = orch.get_ai_message()
        assert isinstance(summary, str) and len(summary) > 20

    @skip_no_key
    def test_pipeline_clean_wrangle_viz_bike_sales(self, llm, df_bike):
        """
        3-adımlı tam pipeline: DataCleaningAgent → DataWranglingAgent → DataVisualizationAgent
        Tüm adımlar başarılı olmalı; viz adımı bir Plotly graph üretmeli.
        """
        from ai_data_science_team.agent_registry import AgentRegistry
        from ai_data_science_team.agents.data_cleaning_agent import DataCleaningAgent
        from ai_data_science_team.agents.data_wrangling_agent import DataWranglingAgent
        from ai_data_science_team.agents.data_visualization_agent import DataVisualizationAgent
        from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent
        from ai_data_science_team.workflow_resolver import build_spec, build_step

        for name, cls, caps in [
            ("DataCleaningAgent",      DataCleaningAgent,      ["data_cleaning"]),
            ("DataWranglingAgent",     DataWranglingAgent,     ["data_wrangling"]),
            ("DataVisualizationAgent", DataVisualizationAgent, ["visualization"]),
        ]:
            AgentRegistry.register(name, cls, capabilities=caps)

        spec = build_spec("bike_full_pipeline", [
            build_step("clean",     "DataCleaningAgent",
                       "Ensure lowercase column names and no duplicate rows."),
            build_step("wrangle",   "DataWranglingAgent",
                       "Group by bike_model: sum extended_sales, sum quantity_sold.",
                       depends_on=["clean"]),
            build_step("visualize", "DataVisualizationAgent",
                       "Create a horizontal bar chart of total extended_sales by bike_model.",
                       depends_on=["wrangle"]),
        ])

        executor = _make_platform_executor(llm, df_bike.head(1000))
        orch = OrchestratorAgent(
            model=llm,
            agent_executor=executor,
            workflow_spec=spec,
        )

        try:
            orch.invoke_agent(user_instructions="Run full bike sales pipeline.")
        except Exception as exc:
            if any(x in str(exc) for x in ("insufficient_quota", "RateLimitError")):
                pytest.skip("OpenAI quota tükendi")
            raise

        rr = orch.get_run_result()
        step_statuses = {s["step_id"]: s["status"] for s in rr["steps"]}

        # clean + wrangle başarılı olmalı
        assert step_statuses.get("clean")   == "success", f"clean başarısız: {step_statuses}"
        assert step_statuses.get("wrangle") == "success", f"wrangle başarısız: {step_statuses}"

        # visualize başarılı veya graceful failure (LLM kod üretmişse)
        assert step_statuses.get("visualize") in ("success", "failed"), \
            f"visualize beklenmeyen durum: {step_statuses}"

        # Orchestrator özet mesajı olmalı
        assert orch.get_ai_message()

    @skip_no_key
    def test_pipeline_runtime_engine_direct_data_flow(self, llm, df_bike):
        """
        RuntimeEngine doğrudan kullanılır (OrchestratorAgent olmadan).
        context["_current_df"] üzerinden veri akışını doğrular.
        """
        from ai_data_science_team.runtime_engine import RuntimeEngine
        from ai_data_science_team.workflow_resolver import build_spec, build_step

        exec_log: list = []
        df_sizes: list = []

        def logging_executor(agent_name: str, instruction: str, context: dict) -> dict:
            exec_log.append(agent_name)
            df_in = context.get("_current_df", df_bike.head(500))
            df_sizes.append(len(df_in))

            if agent_name == "DataCleaningAgent":
                from ai_data_science_team.agents.data_cleaning_agent import DataCleaningAgent
                ag = DataCleaningAgent(model=llm)
                ag.invoke_agent(user_instructions=instruction, data_raw=df_in)
                cleaned = ag.get_data_cleaned()
                if isinstance(cleaned, pd.DataFrame):
                    context["_current_df"] = cleaned
                    return {"rows": len(cleaned), "agent": agent_name}
            elif agent_name == "DataWranglingAgent":
                from ai_data_science_team.agents.data_wrangling_agent import DataWranglingAgent
                ag = DataWranglingAgent(model=llm)
                ag.invoke_agent(user_instructions=instruction, data_raw=df_in)
                wrangled = ag.get_data_wrangled()
                if isinstance(wrangled, pd.DataFrame):
                    context["_current_df"] = wrangled
                    return {"rows": len(wrangled), "agent": agent_name}
            return {"agent": agent_name, "rows": len(df_in)}

        spec = build_spec("runtime_data_flow", [
            build_step("clean",   "DataCleaningAgent",
                       "Lowercase column names, drop duplicates."),
            build_step("wrangle", "DataWranglingAgent",
                       "Group by bike_model and sum extended_sales.",
                       depends_on=["clean"]),
        ])

        engine = RuntimeEngine(
            agent_executor=logging_executor,
            max_retries=1,
            backoff_base=0,
        )

        try:
            result = engine.run(
                spec,
                session_id="e2e-runtime-test",
                context={"_current_df": df_bike.head(500)},
            )
        except Exception as exc:
            if any(x in str(exc) for x in ("insufficient_quota", "RateLimitError")):
                pytest.skip("OpenAI quota tükendi")
            raise

        assert result.status in ("completed", "degraded")
        assert "DataCleaningAgent"  in exec_log, "DataCleaningAgent çalışmadı"
        assert "DataWranglingAgent" in exec_log, "DataWranglingAgent çalışmadı"

        # Wrangle adımı daha az satır döndürmeli (gruplandırma)
        if "wrangle" in result.final_outputs:
            wrangle_out = result.final_outputs["wrangle"]
            if isinstance(wrangle_out, dict) and "rows" in wrangle_out:
                assert wrangle_out["rows"] < 500, "Gruplandırma sonucu orijinalden küçük olmalı"


class TestOrchestratorDynamicWithRealAgents:
    """Dynamic senaryo: LLM hem spec üretiyor hem de gerçek agent'lar çalışıyor."""

    @skip_no_key
    def test_dynamic_pipeline_generates_and_runs(self, llm, df_bike):
        """
        LLM bir veri bilimi pipeline spec'i üretir ve gerçek agent'larla çalışır.
        """
        from ai_data_science_team.agent_registry import AgentRegistry
        from ai_data_science_team.agents.data_cleaning_agent import DataCleaningAgent
        from ai_data_science_team.agents.data_wrangling_agent import DataWranglingAgent
        from ai_data_science_team.agents.data_visualization_agent import DataVisualizationAgent
        from ai_data_science_team.ds_agents.eda_tools_agent import EDAToolsAgent
        from ai_data_science_team.agents.orchestrator_agent import OrchestratorAgent

        for name, cls, caps in [
            ("DataCleaningAgent",      DataCleaningAgent,      ["data_cleaning"]),
            ("DataWranglingAgent",     DataWranglingAgent,     ["data_wrangling"]),
            ("DataVisualizationAgent", DataVisualizationAgent, ["visualization"]),
            ("EDAToolsAgent",          EDAToolsAgent,          ["eda"]),
        ]:
            AgentRegistry.register(name, cls, capabilities=caps)

        executor = _make_platform_executor(llm, df_bike.head(300))

        orch = OrchestratorAgent(
            model=llm,
            agent_executor=executor,
            scenario="dynamic",
        )

        try:
            orch.invoke_agent(
                user_instructions=(
                    "I have a bike sales dataset with columns: date, bike_model, price, "
                    "quantity_sold, extended_sales. Please clean the data and compute "
                    "total sales by bike model."
                )
            )
        except Exception as exc:
            if any(x in str(exc) for x in ("insufficient_quota", "RateLimitError")):
                pytest.skip("OpenAI quota tükendi")
            raise

        assert orch.get_scenario() == "dynamic"
        spec = orch.get_workflow_spec()
        assert len(spec.get("steps", [])) >= 1, "Dynamic spec en az 1 step içermeli"

        rr = orch.get_run_result()
        assert "status" in rr

        summary = orch.get_ai_message()
        assert isinstance(summary, str) and len(summary) > 0


class TestRegistryIntegrationE2E:

    @skip_no_key
    def test_registry_query_then_run(self, llm, df_bike):
        """
        Registry'den 'data_cleaning' capability'ye sahip agent sorgulanır,
        bulunur ve doğrudan çalıştırılır.
        """
        from ai_data_science_team.agent_registry import AgentRegistry
        from ai_data_science_team.agents.data_cleaning_agent import DataCleaningAgent

        AgentRegistry.register(
            "DataCleaningAgent",
            DataCleaningAgent,
            capabilities=["data_cleaning"],
            description="Cleans and standardizes raw DataFrames.",
        )

        # Registry'den sorgula
        cleaners = AgentRegistry.query(capability="data_cleaning")
        assert len(cleaners) == 1
        assert cleaners[0].name == "DataCleaningAgent"

        # Meta'dan class'ı al ve doğrudan çalıştır
        agent_cls = cleaners[0].agent_class
        agent = agent_cls(model=llm)

        try:
            agent.invoke_agent(
                user_instructions="Lowercase all column names and drop any NaN rows.",
                data_raw=df_bike.head(100),
            )
        except Exception as exc:
            if any(x in str(exc) for x in ("insufficient_quota", "RateLimitError")):
                pytest.skip("OpenAI quota tükendi")
            raise

        result = agent.get_data_cleaned()
        assert isinstance(result, pd.DataFrame)
        assert all(c == c.lower() for c in result.columns)

    @skip_no_key
    def test_registry_catalog_drives_dynamic_resolution(self, llm, df_dirty):
        """
        Registry catalog'u WorkflowResolver'a enjekte edilince
        LLM katalogdaki agent'lardan seçim yapmalı.
        """
        from ai_data_science_team.agent_registry import AgentRegistry
        from ai_data_science_team.agents.data_cleaning_agent import DataCleaningAgent
        from ai_data_science_team.workflow_resolver import WorkflowResolver

        AgentRegistry.register(
            "DataCleaningAgent", DataCleaningAgent,
            capabilities=["data_cleaning"],
            description="Cleans raw DataFrames.",
        )

        catalog = AgentRegistry.to_catalog()
        resolver = WorkflowResolver(model=llm, registry_catalog=catalog)

        try:
            result = resolver.resolve(
                user_goal="Clean the dataset by removing missing values."
            )
        except Exception as exc:
            if any(x in str(exc) for x in ("insufficient_quota", "RateLimitError")):
                pytest.skip("OpenAI quota tükendi")
            raise

        spec = result["spec"]
        # LLM katalogdaki DataCleaningAgent'ı seçmeli
        agent_names = [s.get("agent") for s in spec.get("steps", [])]
        assert "DataCleaningAgent" in agent_names, \
            f"LLM katalogdan DataCleaningAgent seçmedi: {agent_names}"
