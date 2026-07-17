from __future__ import annotations

"""Auto-generated h2o node module.

Extracted from the 3,400-line ``supervisor_ds_team.py`` monolith
during the L2 code-review remediation pass.  Uses dependency
injection via the ``H2oNodeDeps`` dataclass.
"""

import logging  # noqa: E402, F401
from dataclasses import dataclass  # noqa: E402, F401
from typing import Any, Callable  # noqa: E402, F401

from langchain_core.messages import AIMessage  # noqa: E402, F401

from ai_data_science_team.multiagents.supervisor import (  # noqa: E402, F401
    SupervisorDSState)

logger = logging.getLogger(__name__)


@dataclass
class H2oNodeDeps:
    """Dependencies for the h2o node."""
    h2o_ml_agent: Any
    append_error_message: Any  # was _append_error_message
    ensure_dataset_registry: Any  # was _ensure_dataset_registry
    ensure_df: Any  # was _ensure_df
    format_result_with_llm: Any  # was _format_result_with_llm
    get_active_data: Any  # was _get_active_data
    _get_last_human_text: Any  # was _get_last_human
    is_empty_df: Any  # was _is_empty_df
    merge_messages: Any  # was _merge_messages
    register_dataset: Any  # was _register_dataset
    tag_messages: Any  # was _tag_messages
    llm: Any


def make_node_h2o(deps: H2oNodeDeps) -> Callable[[SupervisorDSState], dict]:
    """Build the ``node_h2o`` state-graph node."""

    def node_h2o(state: SupervisorDSState):
        logger.info("---H2O ML---")
        before_msgs = list(state.get("messages", []) or [])
        last_human = deps._get_last_human_text(before_msgs)
        # Respect the supervisor's active dataset selection (dataset registry / active_dataset_id),
        # falling back to known state keys when the registry is absent.
        active_df = deps.ensure_df(
            deps.get_active_data(
                state,
                [
                    "feature_data",
                    "data_cleaned",
                    "data_wrangled",
                    "data_sql",
                    "data_raw",
                ])
        )
        if deps.is_empty_df(active_df):
            return {
                "messages": [
                    AIMessage(
                        content="No dataset is available for modeling. Load data and (optionally) engineer features first.",
                        name="h2o_ml_agent")
                ],
                "last_worker": "H2O_ML_Agent",
            }

        # If user asks for prediction/scoring, use an existing model in the H2O cluster
        # instead of retraining AutoML.
        if isinstance(last_human, str) and any(
            w in last_human.lower()
            for w in ("predict", "prediction", "score", "scoring", "inference")
        ):
            import re  # noqa: E402, F401

            def _extract_run_id(text: str) -> str | None:
                t = text or ""
                m = re.search(r"\b([0-9a-f]{32})\b", t, flags=re.IGNORECASE)
                return m.group(1) if m else None

            def _extract_model_id(text: str) -> str | None:
                t = text or ""
                # Prefer backticked/quoted ids
                m = re.search(r"(?:`|\"|')(?P<mid>[^`\"']+)(?:`|\"|')", t)
                if m and m.group("mid"):
                    mid = m.group("mid").strip()
                    if len(mid) >= 8:
                        return mid
                # Common H2O AutoML id patterns
                m = re.search(r"\b([A-Za-z0-9_]+AutoML_[A-Za-z0-9_]+)\b", t)
                if m and m.group(1):
                    return m.group(1).strip()
                m = re.search(r"\b([A-Za-z0-9_]+_AutoML_[A-Za-z0-9_]+_model_\d+)\b", t)
                if m and m.group(1):
                    return m.group(1).strip()
                return None

            model_id = _extract_model_id(last_human)
            h2o_art = (state.get("artifacts") or {}).get("h2o")
            h2o_art = h2o_art if isinstance(h2o_art, dict) else {}
            cfg = (state.get("artifacts") or {}).get("config") or {}
            cfg = cfg if isinstance(cfg, dict) else {}
            run_id = _extract_run_id(last_human) or h2o_art.get("mlflow_run_id")
            wants_mlflow = "mlflow" in (last_human or "").lower() or bool(run_id)
            if not model_id:
                model_id = h2o_art.get("best_model_id") or None
            if not model_id and isinstance(h2o_art.get("h2o_train_result"), dict):
                model_id = h2o_art["h2o_train_result"].get("best_model_id")

            # Optional: score via MLflow (preferred when available), so predictions work across restarts.
            if wants_mlflow:
                # If no explicit run_id, try newest run in the configured experiment.
                if not (isinstance(run_id, str) and run_id.strip()):
                    try:
                        import mlflow  # noqa: E402, F401
                        from mlflow.tracking import MlflowClient  # noqa: E402, F401

                        tracking_uri = cfg.get("mlflow_tracking_uri")
                        if isinstance(tracking_uri, str) and tracking_uri.strip():
                            mlflow.set_tracking_uri(tracking_uri.strip())
                        exp_name = cfg.get("mlflow_experiment_name") or "H2O AutoML"
                        client = MlflowClient()
                        exp = client.get_experiment_by_name(str(exp_name))
                        if exp is not None:
                            runs = client.search_runs(
                                experiment_ids=[exp.experiment_id],
                                order_by=["attributes.start_time DESC"],
                                max_results=25)

                            def _run_has_model_artifact(rid: str) -> bool:
                                try:
                                    return bool(
                                        client.list_artifacts(rid, path="model")
                                    )
                                except Exception:
                                    return False

                            # Prefer the newest run that actually contains a logged model.
                            for r in runs or []:
                                rid = getattr(getattr(r, "info", None), "run_id", None)
                                if (
                                    isinstance(rid, str)
                                    and rid
                                    and _run_has_model_artifact(rid)
                                ):
                                    run_id = rid
                                    break
                    except Exception:
                        pass

                if isinstance(run_id, str) and run_id.strip():
                    # Best-effort: drop target column if present so we score only features.
                    target = state.get("target_variable")
                    target = (
                        target
                        if isinstance(target, str) and target in active_df.columns
                        else None
                    )
                    x_df = active_df.drop(columns=[target]) if target else active_df
                    try:
                        import mlflow  # noqa: E402, F401
                        import pandas as pd  # noqa: E402, F401
                        import h2o  # noqa: E402, F401
                        from mlflow.tracking import MlflowClient  # noqa: E402, F401

                        tracking_uri = cfg.get("mlflow_tracking_uri")
                        if isinstance(tracking_uri, str) and tracking_uri.strip():
                            mlflow.set_tracking_uri(tracking_uri.strip())

                        model_uri = f"runs:/{run_id.strip()}/model"
                        # Validate this run actually has a model logged; otherwise provide a helpful message.
                        try:
                            client = MlflowClient()
                            has_model = any(
                                getattr(item, "path", None) == "model"
                                for item in client.list_artifacts(
                                    run_id.strip(), path=""
                                )
                            )
                        except Exception:
                            has_model = True
                        if not has_model:
                            return {
                                "messages": [
                                    AIMessage(
                                        content=(
                                            f"MLflow run `{run_id}` does not contain a logged model at artifact path `model/`.\n\n"
                                            "This usually means you logged workflow artifacts (tables/json) but did not log a model. "
                                            "Train with MLflow enabled (H2O training logs to `model/`), or provide a run id that contains a model."
                                        ),
                                        name="h2o_ml_agent")
                                ],
                                "last_worker": "H2O_ML_Agent",
                            }
                        # Prefer mlflow.h2o flavor for stable scoring (handles H2O models and
                        # lets us coerce categorical columns to match training).
                        h2o.init()
                        try:
                            model = mlflow.h2o.load_model(model_uri)
                        except Exception:
                            model = mlflow.pyfunc.load_model(model_uri)

                        if hasattr(model, "predict") and not hasattr(
                            model, "_model_json"
                        ):
                            # Likely a pyfunc wrapper; predict directly.
                            raw_preds = model.predict(x_df)
                            if isinstance(raw_preds, pd.DataFrame):
                                preds_df = raw_preds
                            elif isinstance(raw_preds, pd.Series):
                                preds_df = raw_preds.to_frame(name="prediction")
                            else:
                                preds_df = pd.DataFrame({"prediction": list(raw_preds)})
                        else:
                            frame = h2o.H2OFrame(x_df)
                            # Coerce expected categorical columns to factor.
                            try:
                                out_json = getattr(model, "_model_json", {}) or {}
                                output = (
                                    out_json.get("output")
                                    if isinstance(out_json, dict)
                                    else {}
                                )
                                names = (
                                    output.get("names")
                                    if isinstance(output, dict)
                                    else None
                                )
                                domains = (
                                    output.get("domains")
                                    if isinstance(output, dict)
                                    else None
                                )
                                if isinstance(names, list) and isinstance(
                                    domains, list
                                ):
                                    for col, dom in zip(names, domains):
                                        if dom is None:
                                            continue
                                        if col in frame.columns:
                                            try:
                                                frame[col] = frame[col].asfactor()
                                            except Exception:
                                                pass
                            except Exception:
                                pass

                            preds_h2o = model.predict(frame)
                            preds_df = preds_h2o.as_data_frame(use_pandas=True)

                        try:
                            preds_df.insert(0, "row_id", range(len(preds_df)))
                            if target:
                                preds_df.insert(
                                    1,
                                    f"actual_{target}",
                                    active_df[target].reset_index(drop=True))
                        except Exception:
                            pass

                        preds_data = preds_df.to_dict()
                    except Exception as e:
                        return {
                            "messages": [
                                AIMessage(
                                    content=(
                                        f"Failed to score with MLflow run `{run_id}`: {e}\n\n"
                                        f"Tried model URI: `runs:/{run_id}/model`.\n\n"
                                        "Tip: scoring must use the same feature schema as training. "
                                        "If you trained on engineered features, set the active dataset to that feature dataset before scoring."
                                    ),
                                    name="h2o_ml_agent")
                            ],
                            "last_worker": "H2O_ML_Agent",
                        }

                    datasets, active_dataset_id = deps.ensure_dataset_registry(state)
                    try:
                        label = f"predictions_mlflow_{run_id}"[:80]
                        datasets, active_dataset_id, pred_id = deps.register_dataset(
                            {
                                **state,
                                "datasets": datasets,
                                "active_dataset_id": active_dataset_id,
                            },
                            data=preds_data,
                            stage="wrangled",
                            label=label,
                            created_by="H2O_ML_Agent",
                            provenance={
                                "source_type": "agent",
                                "user_request": last_human,
                                "transform": {
                                    "kind": "mlflow_predict",
                                    "run_id": run_id,
                                    "model_uri": f"runs:/{run_id.strip()}/model",
                                    "dropped_target": bool(target),
                                },
                            },
                            parent_id=active_dataset_id,
                            make_active=True)
                    except Exception:
                        pred_id = None

                    try:
                        preview_md = preds_df.head(5).to_markdown(index=False)
                        msg = f"Scored dataset with MLflow run `{run_id}`. Predictions shape: {preds_df.shape}.\n\n{preview_md}"
                    except Exception:
                        msg = f"Scored dataset with MLflow run `{run_id}`."

                    return {
                        "messages": [AIMessage(content=msg, name="h2o_ml_agent")],
                        "data_wrangled": preds_data,
                        "active_data_key": "data_wrangled",
                        "datasets": datasets,
                        "active_dataset_id": active_dataset_id,
                        "artifacts": {
                            **state.get("artifacts", {}),
                            "mlflow_predictions": {
                                "run_id": run_id,
                                "predictions_dataset_id": pred_id,
                            },
                        },
                        "last_worker": "H2O_ML_Agent",
                    }
            if not isinstance(model_id, str) or not model_id.strip():
                return {
                    "messages": [
                        AIMessage(
                            content=(
                                "To make predictions, provide an H2O `model_id` (or train a model first). "
                                "Example: `predict with model `XGBoost_grid_...` on the dataset`."
                            ),
                            name="h2o_ml_agent")
                    ],
                    "last_worker": "H2O_ML_Agent",
                }

            # Best-effort: drop target column if present so we score only features.
            target = state.get("target_variable")
            target = (
                target
                if isinstance(target, str) and target in active_df.columns
                else None
            )
            x_df = active_df.drop(columns=[target]) if target else active_df

            try:
                import h2o  # noqa: E402, F401

                h2o.init()
                model = h2o.get_model(model_id.strip())
                frame = h2o.H2OFrame(x_df)
                preds_h2o = model.predict(frame)
                preds_df = preds_h2o.as_data_frame(use_pandas=True)
                try:
                    preds_df.insert(0, "row_id", range(len(preds_df)))
                    if target:
                        preds_df.insert(
                            1,
                            f"actual_{target}",
                            active_df[target].reset_index(drop=True))
                except Exception:
                    pass
                preds_data = preds_df.to_dict()
            except Exception as e:
                return {
                    "messages": [
                        AIMessage(
                            content=(
                                f"Failed to score with model `{model_id}`: {e}\n\n"
                                "Tip: model IDs are only available while the H2O cluster is running. "
                                "If you restarted, retrain or load a saved model."
                            ),
                            name="h2o_ml_agent")
                    ],
                    "last_worker": "H2O_ML_Agent",
                }

            # Register predictions as a new dataset (tabular output) for downstream viz/EDA.
            datasets, active_dataset_id = deps.ensure_dataset_registry(state)
            try:
                label = f"predictions_{model_id}"[:80]
                datasets, active_dataset_id, pred_id = deps.register_dataset(
                    {
                        **state,
                        "datasets": datasets,
                        "active_dataset_id": active_dataset_id,
                    },
                    data=preds_data,
                    stage="wrangled",
                    label=label,
                    created_by="H2O_ML_Agent",
                    provenance={
                        "source_type": "agent",
                        "user_request": last_human,
                        "transform": {
                            "kind": "h2o_predict",
                            "model_id": model_id,
                            "dropped_target": bool(target),
                            "n_rows": int(getattr(x_df, "shape", (0, 0))[0] or 0),
                            "n_cols": int(getattr(x_df, "shape", (0, 0))[1] or 0),
                        },
                    },
                    parent_id=active_dataset_id,
                    make_active=True)
            except Exception:
                pred_id = None

            try:
                preview_md = preds_df.head(5).to_markdown(index=False)
                msg = f"Scored dataset with model `{model_id}`. Predictions shape: {preds_df.shape}.\n\n{preview_md}"
            except Exception:
                msg = f"Scored dataset with model `{model_id}`."

            return {
                "messages": [AIMessage(content=msg, name="h2o_ml_agent")],
                "data_wrangled": preds_data,
                "active_data_key": "data_wrangled",
                "datasets": datasets,
                "active_dataset_id": active_dataset_id,
                "artifacts": {
                    **state.get("artifacts", {}),
                    "h2o_predictions": {
                        "model_id": model_id,
                        "predictions_dataset_id": pred_id,
                    },
                },
                "last_worker": "H2O_ML_Agent",
            }

        deps.h2o_ml_agent.invoke_messages(
            messages=before_msgs,
            user_instructions=last_human,
            data_raw=active_df,
            target_variable=state.get("target_variable"))
        response = deps.h2o_ml_agent.response or {}
        merged = deps.merge_messages(before_msgs, response)
        merged["messages"] = deps.tag_messages(merged.get("messages"), "h2o_ml_agent")
        summary_text = deps.format_result_with_llm(
            "h2o_ml_agent",
            response.get("leaderboard"),
            deps._get_last_human_text(before_msgs),
            extra_text="H2O AutoML results.")
        if summary_text:
            merged["messages"].append(
                AIMessage(content=summary_text, name="h2o_ml_agent")
            )
        deps.append_error_message(
            merged,
            "h2o_ml_agent",
            response.get("h2o_train_error"),
            response.get("h2o_train_error_log_path"),
            prefix="Model training error")
        mlflow_run_id = response.get("mlflow_run_id")
        if mlflow_run_id:
            merged["messages"].append(
                AIMessage(
                    content=f"MLflow logging enabled. Run ID: `{mlflow_run_id}`",
                    name="h2o_ml_agent")
            )
            model_uri = response.get("mlflow_model_uri")
            if isinstance(model_uri, str) and model_uri.strip():
                merged["messages"].append(
                    AIMessage(
                        content=f"MLflow model URI: `{model_uri.strip()}`",
                        name="h2o_ml_agent")
                )
        leaderboard = response.get("leaderboard")
        return {
            **merged,
            "model_info": leaderboard,
            "mlflow_artifacts": response.get("mlflow_model")
            or (
                {
                    "run_id": mlflow_run_id,
                    "model_uri": response.get("mlflow_model_uri"),
                }
                if mlflow_run_id
                else None
            ),
            "artifacts": {
                **state.get("artifacts", {}),
                "h2o": response,
                "h2o_details": {
                    "h2o_train_error": response.get("h2o_train_error"),
                    "h2o_train_error_log_path": response.get(
                        "h2o_train_error_log_path"
                    ),
                    "best_model_id": response.get("best_model_id"),
                    "leaderboard": response.get("leaderboard"),
                    "mlflow_run_id": mlflow_run_id,
                    "mlflow_model_uri": response.get("mlflow_model_uri"),
                },
            },
            "last_worker": "H2O_ML_Agent",
        }


    return node_h2o



__all__ = ["H2oNodeDeps", "make_node_h2o"]
