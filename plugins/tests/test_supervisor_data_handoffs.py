from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

from ai_data_science_team.multiagents.supervisor_ds_team import make_supervisor_ds_team


def _df(data: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(data)


@dataclass
class PlannerStub:
    steps: list[str]
    target_variable: str | None = None
    response: dict[str, Any] = field(default_factory=dict)

    def invoke_messages(self, messages, context=None, **kwargs):
        self.response = {
            "steps": list(self.steps),
            "target_variable": self.target_variable,
        }


@dataclass
class RecordingAgent:
    response_factory: Callable[..., dict[str, Any]]
    calls: list[dict[str, Any]] = field(default_factory=list)
    response: dict[str, Any] = field(default_factory=dict)

    def invoke_messages(self, messages, **kwargs):
        recorded = dict(kwargs)
        data_raw = recorded.get("data_raw")
        if isinstance(data_raw, dict):
            recorded["data_raw"] = pd.DataFrame(data_raw)
        self.calls.append(recorded)
        self.response = self.response_factory(**kwargs)


class NoOpAgent:
    def __init__(self):
        self.response: dict[str, Any] = {}

    def invoke_messages(self, messages, **kwargs):
        self.response = {"messages": [AIMessage(content="noop", name="noop_agent")]}


def _make_team(*, planner, cleaning, eda, feature, h2o, wrangling=None):
    dummy_llm = RunnableLambda(lambda _: "FINISH")
    return make_supervisor_ds_team(
        model=dummy_llm,
        workflow_planner_agent=planner,
        data_loader_agent=NoOpAgent(),
        data_wrangling_agent=wrangling or NoOpAgent(),
        data_cleaning_agent=cleaning,
        eda_tools_agent=eda,
        data_visualization_agent=NoOpAgent(),
        sql_database_agent=NoOpAgent(),
        feature_engineering_agent=feature,
        h2o_ml_agent=h2o,
        mlflow_tools_agent=NoOpAgent(),
        model_evaluation_agent=NoOpAgent(),
        temperature=0.0,
    )


def _invoke(app, prompt: str, **state):
    return app.invoke(
        {
            "messages": [HumanMessage(content=prompt)],
            "artifacts": {"config": {"proactive_workflow_mode": True}},
            **state,
        }
    )


class TestSupervisorDataHandoffs:
    def test_eda_does_not_replace_active_dataset_before_cleaning(self):
        raw_df = _df({"a": [1, 2], "b": [10, 20]})

        planner = PlannerStub(["eda", "clean"])
        eda = RecordingAgent(
            lambda **kwargs: {
                "messages": [AIMessage(content="eda", name="eda_tools_agent")],
                "eda_artifacts": {"describe_dataset": {"rows": 2}},
            }
        )
        cleaning = RecordingAgent(
            lambda **kwargs: {
                "messages": [AIMessage(content="clean", name="data_cleaning_agent")],
                "data_cleaned": raw_df.to_dict(),
            }
        )
        app = _make_team(
            planner=planner,
            cleaning=cleaning,
            eda=eda,
            feature=NoOpAgent(),
            h2o=NoOpAgent(),
        )

        result = _invoke(app, "Analyze the data, then clean it.", data_raw=raw_df.to_dict())

        assert len(eda.calls) == 1
        assert len(cleaning.calls) == 1
        pd.testing.assert_frame_equal(eda.calls[0]["data_raw"], raw_df)
        pd.testing.assert_frame_equal(cleaning.calls[0]["data_raw"], raw_df)
        assert result["active_data_key"] == "data_cleaned"

    def test_cleaned_output_flows_into_feature_engineering(self):
        raw_df = _df({"a": [1, None], "b": [10, 20]})
        cleaned_df = _df({"a": [1, 0], "b": [10, 20]})
        feature_df = _df({"a": [1, 0], "b": [10, 20], "a_times_b": [10, 0], "Churn": ["No", "Yes"]})

        planner = PlannerStub(["clean", "feature"], target_variable="Churn")
        cleaning = RecordingAgent(
            lambda **kwargs: {
                "messages": [AIMessage(content="clean", name="data_cleaning_agent")],
                "data_cleaned": cleaned_df.to_dict(),
            }
        )
        feature = RecordingAgent(
            lambda **kwargs: {
                "messages": [AIMessage(content="feature", name="feature_engineering_agent")],
                "data_engineered": feature_df.to_dict(),
            }
        )
        app = _make_team(
            planner=planner,
            cleaning=cleaning,
            eda=NoOpAgent(),
            feature=feature,
            h2o=NoOpAgent(),
        )

        result = _invoke(
            app,
            "Clean the data and engineer features for churn prediction.",
            data_raw=raw_df.to_dict(),
        )

        assert len(cleaning.calls) == 1
        assert len(feature.calls) == 1
        pd.testing.assert_frame_equal(cleaning.calls[0]["data_raw"], raw_df)
        pd.testing.assert_frame_equal(feature.calls[0]["data_raw"], cleaned_df)
        assert feature.calls[0]["target_variable"] == "Churn"
        assert result["active_data_key"] == "feature_data"

    def test_feature_output_flows_into_h2o_model(self):
        raw_df = _df({"a": [1, 0], "b": [10, 20], "Churn": ["No", "Yes"]})
        feature_df = _df(
            {
                "a": [1, 0],
                "b": [10, 20],
                "a_times_b": [10, 0],
                "Churn": ["No", "Yes"],
            }
        )

        planner = PlannerStub(["feature", "model"], target_variable="Churn")
        feature = RecordingAgent(
            lambda **kwargs: {
                "messages": [AIMessage(content="feature", name="feature_engineering_agent")],
                "data_engineered": feature_df.to_dict(),
            }
        )
        h2o = RecordingAgent(
            lambda **kwargs: {
                "messages": [AIMessage(content="model", name="h2o_ml_agent")],
                "leaderboard": {"model_id": {0: "GBM_1"}, "auc": {0: 0.88}},
                "best_model_id": "GBM_1",
            }
        )
        app = _make_team(
            planner=planner,
            cleaning=NoOpAgent(),
            eda=NoOpAgent(),
            feature=feature,
            h2o=h2o,
        )

        result = _invoke(
            app,
            "Engineer features and then train a churn model.",
            data_raw=raw_df.to_dict(),
            target_variable="Churn",
        )

        assert len(feature.calls) == 1
        assert len(h2o.calls) == 1
        pd.testing.assert_frame_equal(feature.calls[0]["data_raw"], raw_df)
        pd.testing.assert_frame_equal(h2o.calls[0]["data_raw"], feature_df)
        assert h2o.calls[0]["target_variable"] == "Churn"
        assert result["artifacts"]["h2o"]["best_model_id"] == "GBM_1"

    def test_wrangled_output_flows_into_cleaning(self):
        raw_df = _df({"a": [1, 1, 2], "b": [10, 10, 20]})
        wrangled_df = _df({"a": [1, 2], "b_total": [20, 20]})
        cleaned_df = _df({"a": [1, 2], "b_total": [20, 20]})

        planner = PlannerStub(["wrangle", "clean"])
        wrangling = RecordingAgent(
            lambda **kwargs: {
                "messages": [AIMessage(content="wrangle", name="data_wrangling_agent")],
                "data_wrangled": wrangled_df.to_dict(),
            }
        )
        cleaning = RecordingAgent(
            lambda **kwargs: {
                "messages": [AIMessage(content="clean", name="data_cleaning_agent")],
                "data_cleaned": cleaned_df.to_dict(),
            }
        )
        app = _make_team(
            planner=planner,
            cleaning=cleaning,
            eda=NoOpAgent(),
            feature=NoOpAgent(),
            h2o=NoOpAgent(),
            wrangling=wrangling,
        )

        result = _invoke(app, "Aggregate first, then clean the result.", data_raw=raw_df.to_dict())

        assert len(wrangling.calls) == 1
        assert len(cleaning.calls) == 1
        pd.testing.assert_frame_equal(wrangling.calls[0]["data_raw"], raw_df)
        pd.testing.assert_frame_equal(cleaning.calls[0]["data_raw"], wrangled_df)
        assert result["active_data_key"] == "data_cleaned"
