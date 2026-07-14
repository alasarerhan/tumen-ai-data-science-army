"""MLflow logging node.

Provides :func:`make_node_mlflow_log` — a factory that returns a
state-graph node function for the MLflow logging sub-agent.

The node body was extracted from the 3,400-line
``supervisor_ds_team.py`` monolith during the L2 code-review
remediation pass.  It uses dependency injection (rather than
closures) so that the function is testable in isolation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from langchain_core.messages import AIMessage

from ai_data_science_team.multiagents.supervisor import (
    SupervisorDSState,
    ensure_df,
    get_active_data,
    is_empty_df,
    tag_messages,
)

logger = logging.getLogger(__name__)


@dataclass
class MlflowLogNodeDeps:
    """Dependencies for the mlflow_log node."""
    mlflow_tools_agent: Any
    ensure_df: Any  # was _ensure_df
    get_active_data: Any  # was _get_active_data
    is_empty_df: Any  # was _is_empty_df
    tag_messages: Any  # was _tag_messages


def make_node_mlflow_log(deps: MlflowLogNodeDeps) -> Callable[[SupervisorDSState], dict]:
    """Build the ``node_mlflow_log`` state-graph node."""

    def node_mlflow_log(state: SupervisorDSState):
        before_msgs = list(state.get("messages", []) or [])

        # Pull config from the supervisor artifacts (optional).
        cfg: dict[str, Any] = {}
        try:
            cfg = (state.get("artifacts") or {}).get("config") or {}
        except Exception:
            cfg = {}

        tracking_uri = cfg.get("mlflow_tracking_uri") if isinstance(cfg, dict) else None
        artifact_root = (
            cfg.get("mlflow_artifact_root") if isinstance(cfg, dict) else None
        )
        experiment_name = (
            cfg.get("mlflow_experiment_name") if isinstance(cfg, dict) else None
        )

        # Attempt to reuse an existing run id (from H2O training) if present.
        run_id = None
        h2o_art = (state.get("artifacts") or {}).get("h2o")
        if isinstance(h2o_art, dict):
            run_id = h2o_art.get("mlflow_run_id")
            if not run_id and isinstance(h2o_art.get("h2o_train_result"), dict):
                run_id = h2o_art["h2o_train_result"].get("mlflow_run_id")
            if not run_id and isinstance(h2o_art.get("model_results"), dict):
                run_id = h2o_art["model_results"].get("mlflow_run_id")

        feature_df = deps.ensure_df(state.get("feature_data"))
        active_df = (
            feature_df
            if not deps.is_empty_df(feature_df)
            else deps.ensure_df(
                deps.get_active_data(
                    state, ["data_cleaned", "data_wrangled", "data_sql", "data_raw"]
                )
            )
        )
        viz_graph = state.get("viz_graph")
        eval_payload = (state.get("artifacts") or {}).get("eval")
        eval_artifacts = state.get("eval_artifacts")
        eval_plot = None
        if isinstance(eval_payload, dict):
            eval_plot = eval_payload.get("plotly_graph")

        logged: dict = {"tables": [], "figures": [], "dicts": [], "metrics": []}
        message_lines: list[str] = []

        try:
            import mlflow
            import json
            from pathlib import Path

            if tracking_uri:
                mlflow.set_tracking_uri(tracking_uri)
            if experiment_name:
                # Best-effort: if an artifact root is configured, ensure the experiment exists
                # with that artifact location (applies only when creating new experiments).
                try:
                    from mlflow.tracking import MlflowClient
                    import re

                    if isinstance(artifact_root, str) and artifact_root.strip():
                        root = Path(artifact_root).expanduser().resolve()
                        root.mkdir(parents=True, exist_ok=True)
                        safe_name = re.sub(
                            r"[^A-Za-z0-9._-]+", "_", str(experiment_name)
                        ).strip("_")
                        safe_name = safe_name or "experiment"
                        artifact_location = (root / safe_name).as_uri()
                        client = MlflowClient(tracking_uri=tracking_uri)
                        exp = client.get_experiment_by_name(str(experiment_name))
                        if exp is None:
                            client.create_experiment(
                                name=str(experiment_name),
                                artifact_location=artifact_location,
                            )
                except Exception:
                    pass
                mlflow.set_experiment(experiment_name)

            # Start or resume the run
            with mlflow.start_run(run_id=run_id) as run:
                run_id = run.info.run_id

                # Basic tags/params
                try:
                    mlflow.set_tags(
                        {
                            "app": "supervisor_ds_team",
                            "active_data_key": state.get("active_data_key") or "",
                            "active_dataset_id": state.get("active_dataset_id") or "",
                        }
                    )
                except Exception:
                    pass

                # Log a small dataset preview + schema
                if active_df is not None and not deps.is_empty_df(active_df):
                    try:
                        mlflow.log_table(
                            active_df.head(200),
                            artifact_file="tables/data_preview.json",
                        )
                        logged["tables"].append("tables/data_preview.json")
                    except Exception:
                        pass
                    try:
                        schema = {
                            "columns": [
                                {"name": str(c), "dtype": str(active_df[c].dtype)}
                                for c in list(active_df.columns)
                            ],
                            "shape": list(active_df.shape),
                        }
                        mlflow.log_dict(schema, artifact_file="tables/schema.json")
                        logged["dicts"].append("tables/schema.json")
                    except Exception:
                        pass

                # Log pipeline (dataset lineage + reproduction script)
                try:
                    from ai_data_science_team.utils.pipeline import (
                        build_pipeline_snapshot,
                    )

                    ds = state.get("datasets")
                    ds = ds if isinstance(ds, dict) else {}
                    pipe = build_pipeline_snapshot(
                        ds, active_dataset_id=state.get("active_dataset_id")
                    )
                    if isinstance(pipe, dict) and pipe.get("lineage"):
                        pipe_spec = dict(pipe)
                        script = pipe_spec.pop("script", None)
                        mlflow.log_dict(
                            pipe_spec, artifact_file="pipeline/pipeline_spec.json"
                        )
                        logged["dicts"].append("pipeline/pipeline_spec.json")
                        if isinstance(script, str) and script.strip():
                            if hasattr(mlflow, "log_text"):
                                mlflow.log_text(
                                    script, artifact_file="pipeline/pipeline_repro.py"
                                )
                                logged["dicts"].append("pipeline/pipeline_repro.py")
                            else:
                                mlflow.log_dict(
                                    {"script": script},
                                    artifact_file="pipeline/pipeline_repro.json",
                                )
                                logged["dicts"].append("pipeline/pipeline_repro.json")
                        try:
                            if pipe.get("pipeline_hash"):
                                mlflow.set_tag(
                                    "pipeline_hash", str(pipe.get("pipeline_hash"))
                                )
                        except Exception:
                            pass
                except Exception:
                    pass

                # Log visualization plot (if any)
                if viz_graph:
                    try:
                        mlflow.log_dict(viz_graph, artifact_file="plots/viz.json")
                        logged["dicts"].append("plots/viz.json")
                    except Exception:
                        pass
                    try:
                        import plotly.io as pio

                        fig = pio.from_json(json.dumps(viz_graph))
                        mlflow.log_figure(fig, artifact_file="plots/viz.html")
                        logged["figures"].append("plots/viz.html")
                    except Exception:
                        pass

                # Log evaluation artifacts + metrics + plot
                if eval_artifacts:
                    try:
                        mlflow.log_dict(
                            eval_artifacts,
                            artifact_file="evaluation/eval_artifacts.json",
                        )
                        logged["dicts"].append("evaluation/eval_artifacts.json")
                    except Exception:
                        pass
                    try:
                        metrics = (
                            eval_artifacts.get("metrics")
                            if isinstance(eval_artifacts, dict)
                            else None
                        )
                        if isinstance(metrics, dict):
                            safe = {}
                            for k, v in metrics.items():
                                try:
                                    safe[str(k)] = float(v)
                                except Exception:
                                    continue
                            if safe:
                                mlflow.log_metrics(safe)
                                logged["metrics"].extend(list(safe.keys()))
                    except Exception:
                        pass
                if eval_plot:
                    try:
                        mlflow.log_dict(
                            eval_plot, artifact_file="evaluation/eval_plot.json"
                        )
                        logged["dicts"].append("evaluation/eval_plot.json")
                    except Exception:
                        pass
                    try:
                        import plotly.io as pio

                        fig = pio.from_json(json.dumps(eval_plot))
                        mlflow.log_figure(
                            fig, artifact_file="evaluation/eval_plot.html"
                        )
                        logged["figures"].append("evaluation/eval_plot.html")
                    except Exception:
                        pass

        except Exception as e:
            message_lines.append(f"MLflow logging failed: {e}")

        if run_id:
            message_lines.append(f"Logged workflow artifacts to MLflow run `{run_id}`.")
        if any(logged.values()):
            message_lines.append(
                "Logged: "
                + ", ".join(
                    [
                        *(
                            [f"{len(logged['tables'])} table(s)"]
                            if logged["tables"]
                            else []
                        ),
                        *(
                            [f"{len(logged['figures'])} figure(s)"]
                            if logged["figures"]
                            else []
                        ),
                        *(
                            [f"{len(logged['dicts'])} json artifact(s)"]
                            if logged["dicts"]
                            else []
                        ),
                        *(
                            [f"{len(logged['metrics'])} metric(s)"]
                            if logged["metrics"]
                            else []
                        ),
                    ]
                )
                + "."
            )
        if not message_lines:
            message_lines.append(
                "No artifacts were available to log yet. Train a model and/or create a chart first."
            )

        msg = "\n".join(message_lines)
        merged = {"messages": [AIMessage(content=msg, name="mlflow_logging_agent")]}
        merged["messages"] = deps.tag_messages(
            merged.get("messages"), "mlflow_logging_agent"
        )
        return {
            **merged,
            "mlflow_artifacts": {"run_id": run_id, "logged": logged},
            "artifacts": {
                **state.get("artifacts", {}),
                "mlflow_log": {"run_id": run_id, "logged": logged},
            },
            "last_worker": "MLflow_Logging_Agent",
        }


    return node_mlflow_log



__all__ = ["MlflowLogNodeDeps", "make_node_mlflow_log"]
