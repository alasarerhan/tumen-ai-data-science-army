import logging

import psutil
from langchain.tools import tool
from langgraph.prebuilt import InjectedState
from typing_extensions import Annotated, Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


def _ms_to_iso(ms: int | None) -> str | None:
    if ms is None:
        return None
    try:
        from datetime import datetime, timezone  # noqa: E402, F401

        return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).isoformat()
    except Exception:
        return None


def _escape_md_cell(value: Any) -> str:
    s = "" if value is None else str(value)
    return s.replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _records_to_md_table(records: list[dict], columns: list[str], max_rows: int = 10) -> str:
    if not records:
        return ""
    cols = [c for c in columns if c]
    rows = records[: max_rows if max_rows and max_rows > 0 else len(records)]
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    body = ["| " + " | ".join(_escape_md_cell(r.get(c)) for c in cols) + " |" for r in rows]
    return "\n".join([header, sep] + body)


def _resolve_active_run(
    *,
    run_id: Optional[str] = None,
    tracking_uri: Optional[str] = None,
    registry_uri: Optional[str] = None,
    experiment_name: Optional[str] = None,
    run_name: Optional[str] = None,
    tags: Optional[Dict[str, Any]] = None,
):
    """
    Return a context manager that yields an active MLflow run.

    - If a matching active run exists, reuse it.
    - If a different active run exists, end it and start/resume the requested run.
    """
    from contextlib import nullcontext  # noqa: E402, F401

    import mlflow  # noqa: E402, F401

    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    if registry_uri:
        mlflow.set_registry_uri(registry_uri)
    if experiment_name:
        # Creates the experiment if it doesn't exist.
        mlflow.set_experiment(experiment_name)

    active = mlflow.active_run()
    if active and (run_id is None or active.info.run_id == run_id):
        return nullcontext(active)

    if active:
        try:
            mlflow.end_run()
        except Exception as exc:
            logger.warning("mlflow.end_run failed (run_id=%s): %s", run_id, exc)

    return mlflow.start_run(run_id=run_id, run_name=run_name, tags=tags)


@tool(response_format="content_and_artifact")
def mlflow_set_tags(
    tags: Dict[str, Any],
    run_id: Optional[str] = None,
    tracking_uri: Optional[str] = None,
    registry_uri: Optional[str] = None,
    experiment_name: Optional[str] = None,
) -> tuple:
    """
    Set one or more tags on an MLflow run. If run_id is not provided, uses the active run
    or starts a new run under experiment_name.
    """
    logger.info("    * Tool: mlflow_set_tags")
    import mlflow  # noqa: E402, F401

    with _resolve_active_run(
        run_id=run_id,
        tracking_uri=tracking_uri,
        registry_uri=registry_uri,
        experiment_name=experiment_name,
    ) as run:
        mlflow.set_tags(tags or {})
        rid = getattr(run.info, "run_id", None) if run else run_id
    return ("Tags set.", {"run_id": rid, "tags": tags})


@tool(response_format="content_and_artifact")
def mlflow_log_params(
    params: Dict[str, Any],
    run_id: Optional[str] = None,
    tracking_uri: Optional[str] = None,
    registry_uri: Optional[str] = None,
    experiment_name: Optional[str] = None,
) -> tuple:
    """
    Log a batch of parameters to an MLflow run. If run_id is not provided, uses the active run
    or starts a new run under experiment_name.
    """
    logger.info("    * Tool: mlflow_log_params")
    import mlflow  # noqa: E402, F401

    with _resolve_active_run(
        run_id=run_id,
        tracking_uri=tracking_uri,
        registry_uri=registry_uri,
        experiment_name=experiment_name,
    ) as run:
        mlflow.log_params(params or {})
        rid = getattr(run.info, "run_id", None) if run else run_id
    return ("Parameters logged.", {"run_id": rid, "params": params})


@tool(response_format="content_and_artifact")
def mlflow_log_metrics(
    metrics: Dict[str, float],
    step: Optional[int] = None,
    run_id: Optional[str] = None,
    tracking_uri: Optional[str] = None,
    registry_uri: Optional[str] = None,
    experiment_name: Optional[str] = None,
) -> tuple:
    """
    Log a batch of metrics to an MLflow run. If run_id is not provided, uses the active run
    or starts a new run under experiment_name.
    """
    logger.info("    * Tool: mlflow_log_metrics")
    import mlflow  # noqa: E402, F401

    # Ensure metrics are numeric where possible
    safe_metrics: Dict[str, float] = {}
    for k, v in (metrics or {}).items():
        try:
            safe_metrics[str(k)] = float(v)
        except Exception:
            continue

    with _resolve_active_run(
        run_id=run_id,
        tracking_uri=tracking_uri,
        registry_uri=registry_uri,
        experiment_name=experiment_name,
    ) as run:
        mlflow.log_metrics(safe_metrics, step=step)
        rid = getattr(run.info, "run_id", None) if run else run_id
    return ("Metrics logged.", {"run_id": rid, "metrics": safe_metrics, "step": step})


@tool(response_format="content_and_artifact")
def mlflow_log_table(
    data: Any,
    artifact_file: str,
    run_id: Optional[str] = None,
    tracking_uri: Optional[str] = None,
    registry_uri: Optional[str] = None,
    experiment_name: Optional[str] = None,
) -> tuple:
    """
    Log a table-like object as an MLflow artifact (using mlflow.log_table).

    Parameters
    ----------
    data : Any
        Anything coercible to a pandas DataFrame (dict/list/records).
    artifact_file : str
        Destination artifact path, e.g. "tables/preview.json".
    """
    logger.info("    * Tool: mlflow_log_table")
    import mlflow  # noqa: E402, F401
    import pandas as pd  # noqa: E402, F401

    df = None
    try:
        if isinstance(data, pd.DataFrame):
            df = data
        else:
            df = pd.DataFrame(data)
    except Exception:
        df = pd.DataFrame({"data": [data]})

    with _resolve_active_run(
        run_id=run_id,
        tracking_uri=tracking_uri,
        registry_uri=registry_uri,
        experiment_name=experiment_name,
    ) as run:
        mlflow.log_table(df, artifact_file=artifact_file)
        rid = getattr(run.info, "run_id", None) if run else run_id
    return (
        "Table logged.",
        {"run_id": rid, "artifact_file": artifact_file, "shape": tuple(df.shape)},
    )


@tool(response_format="content_and_artifact")
def mlflow_log_dict(
    data: Dict[str, Any],
    artifact_file: str,
    run_id: Optional[str] = None,
    tracking_uri: Optional[str] = None,
    registry_uri: Optional[str] = None,
    experiment_name: Optional[str] = None,
) -> tuple:
    """
    Log a JSON-serializable dict to MLflow (using mlflow.log_dict).
    """
    logger.info("    * Tool: mlflow_log_dict")
    import mlflow  # noqa: E402, F401

    with _resolve_active_run(
        run_id=run_id,
        tracking_uri=tracking_uri,
        registry_uri=registry_uri,
        experiment_name=experiment_name,
    ) as run:
        mlflow.log_dict(data or {}, artifact_file=artifact_file)
        rid = getattr(run.info, "run_id", None) if run else run_id
    return ("Dict logged.", {"run_id": rid, "artifact_file": artifact_file})


@tool(response_format="content_and_artifact")
def mlflow_log_figure(
    plotly_graph_dict: Dict[str, Any],
    artifact_file: str,
    run_id: Optional[str] = None,
    tracking_uri: Optional[str] = None,
    registry_uri: Optional[str] = None,
    experiment_name: Optional[str] = None,
) -> tuple:
    """
    Log a Plotly figure to MLflow (using mlflow.log_figure).

    Parameters
    ----------
    plotly_graph_dict : dict
        A Plotly figure in dict form (JSON-serializable).
    artifact_file : str
        Destination artifact file path, e.g. "plots/viz.html" or "plots/viz.json".
    """
    logger.info("    * Tool: mlflow_log_figure")
    import json  # noqa: E402, F401

    import mlflow  # noqa: E402, F401
    import plotly.io as pio  # noqa: E402, F401

    fig = None
    try:
        fig = pio.from_json(json.dumps(plotly_graph_dict or {}))
    except Exception:
        fig = None

    with _resolve_active_run(
        run_id=run_id,
        tracking_uri=tracking_uri,
        registry_uri=registry_uri,
        experiment_name=experiment_name,
    ) as run:
        if fig is not None:
            mlflow.log_figure(fig, artifact_file=artifact_file)
        else:
            # Fallback: log the dict as JSON
            mlflow.log_dict(plotly_graph_dict or {}, artifact_file=artifact_file)
        rid = getattr(run.info, "run_id", None) if run else run_id
    return ("Figure logged.", {"run_id": rid, "artifact_file": artifact_file})


@tool(response_format="content_and_artifact")
def mlflow_log_artifact(
    local_path: str,
    artifact_path: Optional[str] = None,
    run_id: Optional[str] = None,
    tracking_uri: Optional[str] = None,
    registry_uri: Optional[str] = None,
    experiment_name: Optional[str] = None,
) -> tuple:
    """
    Log a local file or directory to MLflow (using mlflow.log_artifact(s)).
    """
    logger.info("    * Tool: mlflow_log_artifact")
    import os  # noqa: E402, F401

    import mlflow  # noqa: E402, F401

    with _resolve_active_run(
        run_id=run_id,
        tracking_uri=tracking_uri,
        registry_uri=registry_uri,
        experiment_name=experiment_name,
    ) as run:
        if os.path.isdir(local_path):
            mlflow.log_artifacts(local_path, artifact_path=artifact_path)
        else:
            mlflow.log_artifact(local_path, artifact_path=artifact_path)
        rid = getattr(run.info, "run_id", None) if run else run_id
    return (
        "Artifact logged.",
        {"run_id": rid, "local_path": local_path, "artifact_path": artifact_path},
    )


@tool(response_format="content_and_artifact")
def mlflow_search_experiments(
    filter_string: Optional[str] = None,
    tracking_uri: str | None = None,
    registry_uri: str | None = None,
) -> tuple[str, dict]:
    """
    Search and list existing MLflow experiments.

    Parameters
    ----------
    filter_string : str, optional
        Filter query string (e.g., "name = 'my_experiment'"), defaults to
        searching for all experiments.

    tracking_uri: str, optional
        Address of local or remote tracking server.
        If not provided, defaults
        to the service set by mlflow.tracking.set_tracking_uri. See Where Runs Get Recorded <../tracking.html#where-runs-get-recorded>_ for more info.
    registry_uri: str, optional
        Address of local or remote model registry
        server. If not provided,
        defaults to the service set by mlflow.tracking.set_registry_uri. If no such service was set, defaults to the tracking uri of the client.

    Returns
    -------
    tuple
        - Content string (human readable).
        - Artifact dict with `experiments` as a list of records.
    """
    logger.info("    * Tool: mlflow_search_experiments")
    from mlflow.tracking import MlflowClient  # noqa: E402, F401

    client = MlflowClient(tracking_uri=tracking_uri, registry_uri=registry_uri)
    experiments = client.search_experiments(filter_string=filter_string)
    records: list[dict] = []
    for e in experiments or []:
        d = dict(e)
        records.append(
            {
                "experiment_id": str(d.get("experiment_id") or ""),
                "name": d.get("name"),
                "artifact_location": d.get("artifact_location"),
                "lifecycle_stage": d.get("lifecycle_stage"),
                "creation_time": _ms_to_iso(d.get("creation_time")),
                "last_update_time": _ms_to_iso(d.get("last_update_time")),
            }
        )

    if not records:
        return ("No experiments found.", {"experiments": [], "count": 0})

    table = _records_to_md_table(
        records,
        columns=[
            "experiment_id",
            "name",
            "lifecycle_stage",
            "creation_time",
            "last_update_time",
        ],
        max_rows=15,
    )
    content = f"Found {len(records)} experiment(s).\n\n{table}"
    return (content, {"experiments": records, "count": len(records)})


@tool(response_format="content_and_artifact")
def mlflow_search_runs(
    experiment_ids: Optional[Union[List[str], List[int], str, int]] = None,
    filter_string: Optional[str] = None,
    max_results: int = 5,
    order_by: Optional[List[str]] = None,
    include_details: bool = False,
    tracking_uri: str | None = None,
    registry_uri: str | None = None,
) -> tuple[str, dict]:
    """
    Search runs within one or more MLflow experiments, optionally filtering by a filter_string.

    Parameters
    ----------
    experiment_ids : list or str or int, optional
        One or more Experiment IDs.
    filter_string : str, optional
        MLflow filter expression, e.g. "metrics.rmse < 1.0".
    max_results : int, optional
        Max number of runs to return (default: 5).
    order_by : list[str], optional
        MLflow order-by expressions (default: ["attributes.start_time DESC"]).
    include_details : bool, optional
        If True, include full `metrics`/`params`/`tags` in each run record. Defaults to False.
    tracking_uri: str, optional
        Address of local or remote tracking server.
        If not provided, defaults
        to the service set by mlflow.tracking.set_tracking_uri. See Where Runs Get Recorded <../tracking.html#where-runs-get-recorded>_ for more info.
    registry_uri: str, optional
        Address of local or remote model registry
        server. If not provided,
        defaults to the service set by mlflow.tracking.set_registry_uri. If no such service was set, defaults to the tracking uri of the client.

    Returns
    -------
    tuple
        - Content string (human readable).
        - Artifact dict with `runs` as a list of records.
    """
    logger.info("    * Tool: mlflow_search_runs")
    from mlflow.tracking import MlflowClient  # noqa: E402, F401

    client = MlflowClient(tracking_uri=tracking_uri, registry_uri=registry_uri)

    if experiment_ids is None:
        experiment_ids = []
    if isinstance(experiment_ids, (str, int)):
        experiment_ids = [experiment_ids]  # type: ignore[assignment]

    exp_ids = [str(x) for x in experiment_ids]  # type: ignore[union-attr]
    if order_by is None:
        order_by = ["attributes.start_time DESC"]

    runs = client.search_runs(
        experiment_ids=exp_ids,
        filter_string=filter_string,
        max_results=int(max_results) if max_results is not None else 50,
        order_by=order_by,
    )

    if not runs:
        return ("No runs found.", {"runs": [], "count": 0, "experiment_ids": exp_ids})

    def _kv_preview(d: dict, max_items: int = 8) -> str:
        if not isinstance(d, dict) or not d:
            return ""
        items = []
        for k in sorted(d.keys())[:max_items]:
            v = d.get(k)
            if isinstance(v, float):
                v = round(v, 6)
            items.append(f"{k}={v}")
        suffix = " …" if len(d) > max_items else ""
        return ", ".join(items) + suffix

    records: list[dict] = []
    for run in runs:
        start_ms = getattr(run.info, "start_time", None)
        end_ms = getattr(run.info, "end_time", None)
        duration_s = None
        try:
            if start_ms is not None and end_ms is not None:
                duration_s = max(0.0, (end_ms - start_ms) / 1000.0)
        except Exception:
            duration_s = None

        rid = getattr(run.info, "run_id", None)
        metrics = dict(getattr(run.data, "metrics", {}) or {})
        params = dict(getattr(run.data, "params", {}) or {})
        tags = dict(getattr(run.data, "tags", {}) or {})
        has_model = False
        try:
            if isinstance(rid, str) and rid:
                model_items = client.list_artifacts(rid, path="model")
                has_model = bool(model_items)
        except Exception:
            has_model = False

        run_record = {
            "run_id": rid,
            "run_name": getattr(run.info, "run_name", None),
            "status": getattr(run.info, "status", None),
            "experiment_id": str(getattr(run.info, "experiment_id", "") or ""),
            "user_id": getattr(run.info, "user_id", None),
            "start_time": _ms_to_iso(start_ms),
            "end_time": _ms_to_iso(end_ms),
            "duration_seconds": duration_s,
            "has_model": has_model,
            "model_uri": f"runs:/{rid}/model"
            if (has_model and isinstance(rid, str) and rid)
            else None,
            "params_preview": _kv_preview(params),
            "metrics_preview": _kv_preview(metrics),
        }
        if include_details:
            run_record["artifact_uri"] = getattr(run.info, "artifact_uri", None)
            run_record["metrics"] = metrics
            run_record["params"] = params
            run_record["tags"] = tags

        records.append(run_record)

    table = _records_to_md_table(
        records,
        columns=[
            "run_id",
            "run_name",
            "status",
            "start_time",
            "duration_seconds",
            "has_model",
        ],
        max_rows=min(15, max(1, int(max_results or 5))),
    )
    content = f"Showing {len(records)} most recent run(s) (max_results={max_results}).\n\n{table}"
    return (
        content,
        {
            "runs": records,
            "count": len(records),
            "experiment_ids": exp_ids,
            "filter_string": filter_string,
            "order_by": order_by,
            "max_results": max_results,
            "include_details": include_details,
        },
    )


@tool(response_format="content")
def mlflow_create_experiment(experiment_name: str) -> str:
    """
    Create a new MLflow experiment by name.

    Parameters
    ----------
    experiment_name : str
        The name of the experiment to create.

    Returns
    -------
    str
        The experiment ID or an error message if creation failed.
    """
    logger.info("    * Tool: mlflow_create_experiment")
    from mlflow.tracking import MlflowClient  # noqa: E402, F401

    client = MlflowClient()
    exp_id = client.create_experiment(experiment_name)
    return f"Experiment created with ID: {exp_id}, name: {experiment_name}"


@tool(response_format="content_and_artifact")
def mlflow_predict_from_run_id(
    run_id: str,
    data_raw: Annotated[dict, InjectedState("data_raw")],
    tracking_uri: Optional[str] = None,
) -> tuple:
    """
    Predict using an MLflow model (PyFunc) directly from a given run ID.

    Parameters
    ----------
    run_id : str
        The ID of the MLflow run that logged the model.
    data_raw : dict
        The incoming data as a dictionary.
    tracking_uri : str, optional
        Address of local or remote tracking server.

    Returns
    -------
    tuple
        (user_facing_message, artifact_dict)
    """
    logger.info("    * Tool: mlflow_predict_from_run_id")
    import mlflow  # noqa: E402, F401
    import mlflow.pyfunc  # noqa: E402, F401
    import pandas as pd  # noqa: E402, F401

    # 1. Check if data is loaded
    if not data_raw:
        return (
            "No data provided for prediction. Please use `data_raw` parameter inside of `invoke_agent()` or `ainvoke_agent()`.",
            {},
        )
    df = pd.DataFrame(data_raw)

    # 2. Prepare model URI
    model_uri = f"runs:/{run_id}/model"

    # 3. Load or cache the MLflow model
    model = mlflow.pyfunc.load_model(model_uri)

    # 4. Make predictions
    try:
        preds = model.predict(df)
    except Exception as e:
        return f"Error during inference: {str(e)}", {}

    # 5. Convert predictions to a user-friendly summary + artifact
    if isinstance(preds, pd.DataFrame):
        sample_json = preds.head().to_json(orient="records")
        artifact_dict = preds.to_dict(orient="records")  # entire DF
        message = f"Predictions returned. Sample: {sample_json}"
    elif hasattr(preds, "to_json"):
        # e.g., pd.Series
        sample_json = preds[:5].to_json(orient="records")
        artifact_dict = preds.to_dict()
        message = f"Predictions returned. Sample: {sample_json}"
    elif hasattr(preds, "tolist"):
        # e.g., a NumPy array
        preds_list = preds.tolist()
        artifact_dict = {"predictions": preds_list}
        message = f"Predictions returned. First 5: {preds_list[:5]}"
    else:
        # fallback
        preds_str = str(preds)
        artifact_dict = {"predictions": preds_str}
        message = f"Predictions returned (unrecognized type). Example: {preds_str[:100]}..."

    return (message, artifact_dict)


# MLflow tool to launch gui for mlflow
@tool(response_format="content")
def mlflow_launch_ui(
    port: int = 5000, host: str = "localhost", tracking_uri: Optional[str] = None
) -> str:
    """
    Launch the MLflow UI.

    Parameters
    ----------
    port : int, optional
        The port on which to run the UI.
    host : str, optional
        The host address to bind the UI to.
    tracking_uri : str, optional
        Address of local or remote tracking server.

    Returns
    -------
    str
        Confirmation message.
    """
    logger.info("    * Tool: mlflow_launch_ui")
    import subprocess  # noqa: E402, F401

    # Try binding to the user-specified port first
    allocated_port = _find_free_port(start_port=port, host=host)

    cmd = ["mlflow", "ui", "--host", host, "--port", str(allocated_port)]
    if tracking_uri:
        cmd.extend(["--backend-store-uri", tracking_uri])

    process = subprocess.Popen(cmd)
    return f"MLflow UI launched at http://{host}:{allocated_port}. (PID: {process.pid})"


def _find_free_port(start_port: int, host: str) -> int:
    """
    Find a free port >= start_port on the specified host.
    If the start_port is free, returns start_port, else tries subsequent ports.
    """
    import socket  # noqa: E402, F401

    for port_candidate in range(start_port, start_port + 1000):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, port_candidate))
            except OSError:
                # Port is in use, try the next one
                continue
            # If bind succeeds, it's free
            return port_candidate

    raise OSError(f"No available ports found in the range {start_port}-{start_port + 999}")


@tool(response_format="content")
def mlflow_stop_ui(port: int = 5000) -> str:
    """
    Kill any process currently listening on the given MLflow UI port.
    Requires `pip install psutil`.

    Parameters
    ----------
    port : int, optional
        The port on which the UI is running.
    """
    logger.info("    * Tool: mlflow_stop_ui")
    import psutil  # noqa: E402, F401

    # Attempt to find processes listening on port; on macOS this may require elevated perms.
    try:
        conns = psutil.net_connections(kind="inet")
    except psutil.AccessDenied:
        return (
            "Unable to enumerate network connections (permission denied). "
            "Try running with elevated permissions or stop the MLflow UI manually."
        )
    except Exception as e:
        return f"Failed to inspect network connections: {e}"

    for conn in conns:
        if conn.laddr and conn.laddr.port == port and conn.pid is not None:
            try:
                p = psutil.Process(conn.pid)
                p_name = p.name()
                p.kill()
                return f"Killed process {conn.pid} ({p_name}) listening on port {port}."
            except psutil.NoSuchProcess:
                return "Process was already terminated before we could kill it."
            except psutil.AccessDenied:
                return (
                    f"Process {conn.pid} is listening on port {port} but cannot be killed "
                    "due to insufficient permissions."
                )
            except Exception as e:
                return f"Failed to kill process {conn.pid} on port {port}: {e}"

    return f"No process found listening on port {port}."


@tool(response_format="content_and_artifact")
def mlflow_list_artifacts(
    run_id: str, path: Optional[str] = None, tracking_uri: Optional[str] = None
) -> tuple:
    """
    List artifacts under a given MLflow run.

    Parameters
    ----------
    run_id : str
        The ID of the run whose artifacts to list.
    path : str, optional
        Path within the run's artifact directory to list. Defaults to the root.
    tracking_uri : str, optional
        Custom tracking server URI.

    Returns
    -------
    tuple
        (summary_message, artifact_listing)
    """
    logger.info("    * Tool: mlflow_list_artifacts")
    from mlflow.tracking import MlflowClient  # noqa: E402, F401

    client = MlflowClient(tracking_uri=tracking_uri)
    # If path is None, list the root folder
    artifact_list = client.list_artifacts(run_id, path or "")

    # Convert to a more user-friendly structure
    artifacts_data = []
    for artifact in artifact_list:
        artifacts_data.append(
            {
                "path": artifact.path,
                "is_dir": artifact.is_dir,
                "file_size": artifact.file_size,
            }
        )

    return (f"Found {len(artifacts_data)} artifacts.", artifacts_data)


@tool(response_format="content_and_artifact")
def mlflow_download_artifacts(
    run_id: str,
    path: Optional[str] = None,
    dst_path: Optional[str] = "./downloaded_artifacts",
    tracking_uri: Optional[str] = None,
) -> tuple:
    """
    Download artifacts from MLflow to a local directory.

    Parameters
    ----------
    run_id : str
        The ID of the run whose artifacts to download.
    path : str, optional
        Path within the run's artifact directory to download. Defaults to the root.
    dst_path : str, optional
        Local destination path to store artifacts.
    tracking_uri : str, optional
        MLflow tracking server URI.

    Returns
    -------
    tuple
        (summary_message, artifact_dict)
    """
    logger.info("    * Tool: mlflow_download_artifacts")
    import os  # noqa: E402, F401

    from mlflow.tracking import MlflowClient  # noqa: E402, F401

    client = MlflowClient(tracking_uri=tracking_uri)
    local_path = client.download_artifacts(run_id, path or "", dst_path)

    # Build a recursive listing of what was downloaded
    downloaded_files = []
    for root, dirs, files in os.walk(local_path):
        for f in files:
            downloaded_files.append(os.path.join(root, f))

    message = (
        f"Artifacts for run_id='{run_id}' have been downloaded to: {local_path}. "
        f"Total files: {len(downloaded_files)}."
    )

    return (message, {"downloaded_files": downloaded_files})


@tool(response_format="content_and_artifact")
def mlflow_list_registered_models(
    max_results: int = 100,
    tracking_uri: Optional[str] = None,
    registry_uri: Optional[str] = None,
) -> tuple:
    """
    List all registered models in MLflow's model registry.

    Parameters
    ----------
    max_results : int, optional
        Maximum number of models to return.
    tracking_uri : str, optional
    registry_uri : str, optional

    Returns
    -------
    tuple
        (summary_message, model_list)
    """
    logger.info("    * Tool: mlflow_list_registered_models")
    from mlflow.tracking import MlflowClient  # noqa: E402, F401

    client = MlflowClient(tracking_uri=tracking_uri, registry_uri=registry_uri)
    # The list_registered_models() call can be paginated; for simplicity, we just pass max_results
    models = client.list_registered_models(max_results=max_results)  # type: ignore[attr-defined]

    models_data = []
    for m in models:
        models_data.append(
            {
                "name": m.name,
                "latest_versions": [
                    {
                        "version": v.version,
                        "run_id": v.run_id,
                        "current_stage": v.current_stage,
                    }
                    for v in m.latest_versions
                ],
            }
        )

    return (f"Found {len(models_data)} registered models.", models_data)


@tool(response_format="content_and_artifact")
def mlflow_search_registered_models(
    filter_string: Optional[str] = None,
    order_by: Optional[List[str]] = None,
    max_results: int = 100,
    tracking_uri: Optional[str] = None,
    registry_uri: Optional[str] = None,
) -> tuple:
    """
    Search registered models in MLflow's registry using optional filters.

    Parameters
    ----------
    filter_string : str, optional
        e.g. "name LIKE 'my_model%'" or "tags.stage = 'production'".
    order_by : list, optional
        e.g. ["name ASC"] or ["timestamp DESC"].
    max_results : int, optional
        Max number of results.
    tracking_uri : str, optional
    registry_uri : str, optional

    Returns
    -------
    tuple
        (summary_message, model_dict_list)
    """
    logger.info("    * Tool: mlflow_search_registered_models")
    from mlflow.tracking import MlflowClient  # noqa: E402, F401

    client = MlflowClient(tracking_uri=tracking_uri, registry_uri=registry_uri)
    models = client.search_registered_models(
        filter_string=filter_string, order_by=order_by, max_results=max_results
    )

    models_data = []
    for m in models:
        models_data.append(
            {
                "name": m.name,
                "description": m.description,
                "creation_timestamp": m.creation_timestamp,
                "last_updated_timestamp": m.last_updated_timestamp,
                "latest_versions": [
                    {
                        "version": v.version,
                        "run_id": v.run_id,
                        "current_stage": v.current_stage,
                    }
                    for v in m.latest_versions
                ],
            }
        )

    return (
        f"Found {len(models_data)} models matching filter={filter_string}.",
        models_data,
    )


@tool(response_format="content_and_artifact")
def mlflow_get_model_version_details(
    name: str,
    version: str,
    tracking_uri: Optional[str] = None,
    registry_uri: Optional[str] = None,
) -> tuple:
    """
    Retrieve details about a specific model version in the MLflow registry.

    Parameters
    ----------
    name : str
        Name of the registered model.
    version : str
        Version number of that model.
    tracking_uri : str, optional
    registry_uri : str, optional

    Returns
    -------
    tuple
        (summary_message, version_data_dict)
    """
    logger.info("    * Tool: mlflow_get_model_version_details")
    from mlflow.tracking import MlflowClient  # noqa: E402, F401

    client = MlflowClient(tracking_uri=tracking_uri, registry_uri=registry_uri)
    version_details = client.get_model_version(name, version)

    data = {
        "name": version_details.name,
        "version": version_details.version,
        "run_id": version_details.run_id,
        "creation_timestamp": version_details.creation_timestamp,
        "current_stage": version_details.current_stage,
        "description": version_details.description,
        "status": version_details.status,
    }

    return (f"Model version details retrieved for {name} v{version}", data)


@tool(response_format="content_and_artifact")
def mlflow_get_run_details(
    run_id: str,
    tracking_uri: Optional[str] = None,
    registry_uri: Optional[str] = None,
) -> tuple:
    """
    Retrieve run info, params, metrics, tags, and a shallow artifact listing.
    """
    logger.info("    * Tool: mlflow_get_run_details")
    import pandas as pd  # noqa: E402, F401
    from mlflow.tracking import MlflowClient  # noqa: E402, F401

    client = MlflowClient(tracking_uri=tracking_uri, registry_uri=registry_uri)
    run = client.get_run(run_id)
    info = run.info
    data = run.data

    # Shallow artifact listing at root
    artifacts = client.list_artifacts(run_id, "")
    artifacts_data = [
        {"path": a.path, "is_dir": a.is_dir, "file_size": a.file_size} for a in artifacts
    ]

    flattened = {
        "run_id": info.run_id,
        "run_name": info.run_name,
        "status": info.status,
        "start_time": pd.to_datetime(info.start_time, unit="ms"),
        "end_time": pd.to_datetime(info.end_time, unit="ms") if info.end_time else None,
        "experiment_id": info.experiment_id,
        "user_id": info.user_id,
        "artifact_uri": info.artifact_uri,
        "metrics": data.metrics,
        "params": data.params,
        "tags": data.tags,
        "artifacts": artifacts_data,
    }
    return (f"Details retrieved for run_id='{run_id}'.", flattened)


@tool(response_format="content")
def mlflow_transition_model_version_stage(
    name: str,
    version: str,
    stage: str,
    archive_existing_versions: bool = False,
    tracking_uri: Optional[str] = None,
    registry_uri: Optional[str] = None,
) -> str:
    """
    Transition a registered model version to a new stage (e.g., Staging, Production, Archived).
    """
    logger.info("    * Tool: mlflow_transition_model_version_stage")
    from mlflow.tracking import MlflowClient  # noqa: E402, F401

    client = MlflowClient(tracking_uri=tracking_uri, registry_uri=registry_uri)
    client.transition_model_version_stage(
        name=name,
        version=version,
        stage=stage,
        archive_existing_versions=archive_existing_versions,
    )
    return (
        f"Model '{name}' version '{version}' transitioned to stage '{stage}'. "
        f"archive_existing_versions={archive_existing_versions}"
    )


@tool(response_format="content_and_artifact")
def mlflow_tracking_info() -> tuple:
    """
    Return current tracking URI, registry URI, and active run info (if any).
    """
    logger.info("    * Tool: mlflow_tracking_info")
    import mlflow  # noqa: E402, F401

    tracking_uri = mlflow.get_tracking_uri()
    registry_uri = mlflow.get_registry_uri()
    active = mlflow.active_run()
    active_info = None
    if active:
        active_info = {
            "run_id": active.info.run_id,
            "experiment_id": active.info.experiment_id,
            "artifact_uri": active.info.artifact_uri,
            "status": active.info.status,
        }
    msg = "MLflow tracking info retrieved."
    artifact = {
        "tracking_uri": tracking_uri,
        "registry_uri": registry_uri,
        "active_run": active_info,
    }
    return msg, artifact


@tool(response_format="content_and_artifact")
def mlflow_ui_status(port: int = 5000) -> tuple:
    """
    Check if a process appears to be serving MLflow UI on the given port.
    """
    logger.info("    * Tool: mlflow_ui_status")
    ui_procs = []
    try:
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmdline = proc.info.get("cmdline") or []
                if any("mlflow" in part for part in cmdline) and "ui" in cmdline:
                    ui_procs.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        ui_procs = []

    listening = []
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr and conn.laddr.port == port and conn.pid is not None:
                listening.append(conn.pid)
    except Exception:
        listening = []

    running = any(p["pid"] in listening for p in ui_procs) if ui_procs else bool(listening)
    msg = f"MLflow UI {'appears to be running' if running else 'not detected'} on port {port}."
    return msg, {"ui_processes": ui_procs, "listening_pids_on_port": listening}
