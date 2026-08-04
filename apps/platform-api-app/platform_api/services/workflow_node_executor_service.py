from __future__ import annotations

import json
import math
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from platform_api.core.config import settings
from platform_api.db.models import Artifact, WorkflowNodeExecution, WorkflowRun
from platform_api.services.artifact_storage_service import get_artifact_storage_backend
from platform_api.services.hitl_service import create_hitl_approval


@dataclass(frozen=True)
class NodeExecutionContext:
    db: Session
    run: WorkflowRun
    node: WorkflowNodeExecution


NodeExecutor = Callable[[NodeExecutionContext], dict[str, Any]]


DATASET_ARTIFACT_TYPES = {"dataset", "clean_dataset", "feature_set", "table"}


def get_default_node_executors() -> dict[str, NodeExecutor]:
    return {
        "manual.trigger": _execute_trigger,
        "schedule.trigger": _execute_trigger,
        "webhook.trigger": _execute_trigger,
        "dataset.profile": _execute_dataset_profile,
        "data.clean": _execute_data_clean,
        "feature.engineer": _execute_feature_engineer,
        "model.train": _execute_model_train,
        "model.evaluate": _execute_model_evaluate,
        "report.generate": _execute_report_generate,
        "approval.wait": _execute_approval_wait,
        "artifact.export": _execute_artifact_export,
    }


def _execute_trigger(ctx: NodeExecutionContext) -> dict[str, Any]:
    return {
        "outputs": {
            "trigger_type": ctx.run.trigger_type or "manual",
            "parameters": _run_parameters(ctx.run),
            "input_artifact_ids": _run_input_artifact_ids(ctx.run),
        },
        "logs": ["Trigger context captured."],
    }


def _execute_dataset_profile(ctx: NodeExecutionContext) -> dict[str, Any]:
    dataframe, source = _load_latest_dataframe(ctx)
    sample_rows = int(_node_config(ctx.node).get("sample_rows") or min(len(dataframe), 20))
    profile = _build_dataframe_profile(dataframe, sample_rows=sample_rows)
    uri = _write_json_artifact(
        ctx,
        filename="profile.json",
        payload=profile,
    )
    parent_ids = [str(source.id)] if source else []
    return {
        "outputs": {
            "profile": profile,
            "row_count": profile["row_count"],
            "column_count": profile["column_count"],
        },
        "artifacts": [
            {
                "artifact_type": "profile_report",
                "uri": uri,
                "parent_artifact_ids": parent_ids,
            }
        ],
        "logs": [f"Profiled {profile['row_count']} rows and {profile['column_count']} columns."],
    }


def _execute_data_clean(ctx: NodeExecutionContext) -> dict[str, Any]:
    dataframe, source = _load_latest_dataframe(ctx)
    config = _node_config(ctx.node)
    model = _build_chat_model("data.clean")

    from ai_data_science_team.agents.data_cleaning_agent import DataCleaningAgent

    agent = DataCleaningAgent(model=model)
    agent.invoke_agent(
        data_raw=dataframe,
        user_instructions=config.get("instruction") or config.get("strategy"),
    )
    cleaned = agent.get_data_cleaned()
    if cleaned is None or cleaned.empty:
        raise RuntimeError("DataCleaningAgent did not produce a cleaned dataset")

    uri = _write_dataframe_artifact(ctx, filename="clean_dataset.csv", dataframe=cleaned)
    parent_ids = [str(source.id)] if source else []
    return {
        "outputs": {
            "rows": len(cleaned),
            "columns": list(map(str, cleaned.columns)),
            "recommended_steps": agent.get_recommended_cleaning_steps(),
            "data_cleaner_function": agent.get_data_cleaner_function(),
        },
        "artifacts": [{"artifact_type": "dataset", "uri": uri, "parent_artifact_ids": parent_ids}],
        "logs": [agent.get_log_summary() or "DataCleaningAgent completed."],
    }


def _execute_feature_engineer(ctx: NodeExecutionContext) -> dict[str, Any]:
    dataframe, source = _load_latest_dataframe(ctx)
    config = _node_config(ctx.node)
    model = _build_chat_model("feature.engineer")

    from ai_data_science_team.agents.feature_engineering_agent import FeatureEngineeringAgent

    agent = FeatureEngineeringAgent(model=model)
    agent.invoke_agent(
        data_raw=dataframe,
        user_instructions=config.get("instruction"),
        target_variable=_target_variable(ctx, config),
    )
    engineered = agent.get_data_engineered()
    if engineered is None or engineered.empty:
        raise RuntimeError("FeatureEngineeringAgent did not produce a feature dataset")

    uri = _write_dataframe_artifact(ctx, filename="feature_set.csv", dataframe=engineered)
    parent_ids = [str(source.id)] if source else []
    return {
        "outputs": {
            "rows": len(engineered),
            "columns": list(map(str, engineered.columns)),
            "recommended_steps": agent.get_recommended_feature_engineering_steps(),
            "feature_engineer_function": agent.get_feature_engineer_function(),
        },
        "artifacts": [
            {"artifact_type": "feature_set", "uri": uri, "parent_artifact_ids": parent_ids}
        ],
        "logs": [agent.get_log_summary() or "FeatureEngineeringAgent completed."],
    }


def _execute_model_train(ctx: NodeExecutionContext) -> dict[str, Any]:
    dataframe, source = _load_latest_dataframe(ctx)
    config = _node_config(ctx.node)
    target_variable = _target_variable(ctx, config)
    if not target_variable:
        raise RuntimeError(
            "model.train requires config.target_column or parameters.target_variable"
        )
    if target_variable not in dataframe.columns:
        raise RuntimeError(
            f"Target column '{target_variable}' was not found in the feature dataset"
        )

    model = _build_chat_model("model.train")
    model_dir = _local_node_directory(ctx) / "model"
    model_dir.mkdir(parents=True, exist_ok=True)

    from ai_data_science_team.ml_agents.h2o_ml_agent import H2OMLAgent

    agent = H2OMLAgent(model=model, model_directory=str(model_dir))
    agent.invoke_agent(
        data_raw=dataframe,
        user_instructions=config.get("instruction"),
        target_variable=target_variable,
    )
    leaderboard = agent.get_leaderboard()
    model_manifest = {
        "target_variable": target_variable,
        "best_model_id": agent.get_best_model_id(),
        "model_path": agent.get_model_path(),
        "recommended_steps": agent.get_recommended_ml_steps(),
    }
    if not model_manifest["best_model_id"] and not model_manifest["model_path"]:
        raise RuntimeError("H2OMLAgent did not produce a model reference")

    model_uri = _write_json_artifact(ctx, filename="model_manifest.json", payload=model_manifest)
    artifacts = [
        {
            "artifact_type": "model",
            "uri": model_uri,
            "parent_artifact_ids": [str(source.id)] if source else [],
        }
    ]
    outputs: dict[str, Any] = {"model": model_manifest}
    if leaderboard is not None:
        metrics_uri = _write_dataframe_artifact(
            ctx, filename="leaderboard.csv", dataframe=leaderboard
        )
        artifacts.append(
            {
                "artifact_type": "metrics",
                "uri": metrics_uri,
                "parent_artifact_ids": [str(source.id)] if source else [],
            }
        )
        outputs["leaderboard"] = _dataframe_preview(leaderboard, rows=20)
    return {
        "outputs": outputs,
        "artifacts": artifacts,
        "logs": [agent.get_log_summary() or "H2OMLAgent completed."],
    }


def _execute_model_evaluate(ctx: NodeExecutionContext) -> dict[str, Any]:
    dataframe, source = _load_latest_dataframe(ctx)
    config = _node_config(ctx.node)
    target_variable = _target_variable(ctx, config)
    if not target_variable:
        raise RuntimeError(
            "model.evaluate requires config.target_column or parameters.target_variable"
        )
    model_artifacts = _collect_prior_artifact_payloads(ctx, kinds={"model"})

    from ai_data_science_team.ml_agents.model_evaluation_agent import ModelEvaluationAgent

    agent = ModelEvaluationAgent()
    agent.invoke_messages(
        [],
        data_raw=dataframe,
        model_artifacts=model_artifacts,
        target_variable=target_variable,
        user_instructions=config.get("instruction"),
    )
    evaluation = agent.get_eval_artifacts()
    if not evaluation:
        response = getattr(agent, "response", {}) or {}
        message = ""
        if response.get("messages"):
            message = getattr(response["messages"][-1], "content", "")
        raise RuntimeError(message or "ModelEvaluationAgent did not produce evaluation artifacts")

    uri = _write_json_artifact(ctx, filename="evaluation.json", payload=evaluation)
    parent_ids = [str(source.id)] if source else []
    return {
        "outputs": {"evaluation": evaluation},
        "artifacts": [
            {"artifact_type": "evaluation_report", "uri": uri, "parent_artifact_ids": parent_ids}
        ],
        "logs": ["ModelEvaluationAgent completed."],
    }


def _execute_report_generate(ctx: NodeExecutionContext) -> dict[str, Any]:
    config = _node_config(ctx.node)
    prior_artifacts = _collect_prior_artifact_payloads(ctx)
    model = _build_chat_model("report.generate")

    from ai_data_science_team.agents.strategic_agents import NarrativeAgent

    audience = config.get("audience") or "technical"
    instruction = (
        config.get("instruction")
        or f"Generate a {audience} data science workflow report from the available artifacts."
    )
    agent = NarrativeAgent(model=model)
    agent.invoke_agent(user_instructions=instruction, prior_artifacts=prior_artifacts)
    message = agent.get_ai_message()
    report_text = str(message or "")
    if not report_text:
        artifacts = agent.get_artifacts()
        report_text = json.dumps(_json_safe(artifacts), indent=2)
    if not report_text:
        raise RuntimeError("NarrativeAgent did not produce a report")

    uri = _write_text_artifact(ctx, filename="report.md", content=report_text)
    return {
        "outputs": {"report": report_text, "tool_calls": agent.get_tool_calls()},
        "artifacts": [
            {
                "artifact_type": "report",
                "uri": uri,
                "parent_artifact_ids": list(prior_artifacts.keys()),
            }
        ],
        "logs": ["NarrativeAgent completed."],
    }


def _execute_approval_wait(ctx: NodeExecutionContext) -> dict[str, Any]:
    config = _node_config(ctx.node)
    prior_artifacts = _collect_prior_artifact_payloads(ctx)
    approval = create_hitl_approval(
        ctx.db,
        tenant_id=ctx.run.tenant_id,
        workspace_id=ctx.run.workspace_id,
        workflow_run_id=ctx.run.id,
        step_key=ctx.node.node_id,
        payload={
            "node_id": ctx.node.node_id,
            "node_type": ctx.node.node_type,
            "approver_role": config.get("approver_role"),
            "artifacts": prior_artifacts,
        },
        created_by_user_id=ctx.run.requested_by_user_id,
        expires_hours=int(config.get("expires_hours") or 48),
    )
    return {
        "status": "waiting_approval",
        "outputs": {"approval_id": str(approval.id), "status": str(approval.status.value)},
        "logs": [f"Waiting for approval {approval.id}."],
    }


def _execute_artifact_export(ctx: NodeExecutionContext) -> dict[str, Any]:
    config = _node_config(ctx.node)
    prior_artifacts = _collect_prior_artifacts(ctx)
    if not prior_artifacts:
        raise RuntimeError("artifact.export requires at least one upstream artifact")
    manifest = {
        "format": config.get("format") or "json",
        "artifact_count": len(prior_artifacts),
        "artifacts": [
            {
                "id": str(artifact.id),
                "artifact_type": artifact.kind,
                "uri": artifact.uri,
                "produced_by_node_id": artifact.produced_by_node_id,
            }
            for artifact in prior_artifacts
        ],
    }
    uri = _write_json_artifact(ctx, filename="export_manifest.json", payload=manifest)
    return {
        "outputs": {"export_manifest": manifest},
        "artifacts": [
            {
                "artifact_type": "export_manifest",
                "uri": uri,
                "parent_artifact_ids": [item["id"] for item in manifest["artifacts"]],
            }
        ],
        "logs": [f"Export manifest created for {len(prior_artifacts)} artifact(s)."],
    }


def _build_chat_model(node_type: str) -> Any:
    if not settings.openai_api_key:
        raise RuntimeError(
            f"OPENAI_API_KEY is required to execute LLM-backed workflow node '{node_type}'"
        )
    from langchain_openai import ChatOpenAI

    kwargs: dict[str, Any] = {
        "model": settings.openai_model,
        "temperature": 0,
        "api_key": settings.openai_api_key,
    }
    http_client = _build_trusted_http_client()
    if http_client is not None:
        kwargs["http_client"] = http_client
    return ChatOpenAI(**kwargs)


def _build_trusted_http_client() -> Any | None:
    """Use the OS certificate store when available.

    Windows developer machines often trust corporate/root certificates through
    the OS store while Python's default certifi bundle does not. The worker must
    still verify TLS; this only changes the trust source.
    """
    try:
        import ssl

        import httpx
        import truststore

        return httpx.Client(verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT))
    except Exception:
        return None


def _node_payload(node: WorkflowNodeExecution) -> dict[str, Any]:
    return json.loads(node.inputs_json) if node.inputs_json else {}


def _node_config(node: WorkflowNodeExecution) -> dict[str, Any]:
    payload = _node_payload(node)
    config = payload.get("config")
    if isinstance(config, dict):
        return config
    return payload


def _run_parameters(run: WorkflowRun) -> dict[str, Any]:
    return json.loads(run.parameters_json) if run.parameters_json else {}


def _run_input_artifact_ids(run: WorkflowRun) -> list[str]:
    return [
        str(item)
        for item in (json.loads(run.input_artifact_ids_json) if run.input_artifact_ids_json else [])
    ]


def _target_variable(ctx: NodeExecutionContext, config: dict[str, Any]) -> str | None:
    params = _run_parameters(ctx.run)
    return (
        config.get("target_column")
        or config.get("target_variable")
        or params.get("target_column")
        or params.get("target_variable")
    )


def _load_latest_dataframe(ctx: NodeExecutionContext) -> tuple[Any, Artifact | None]:
    for artifact in reversed(_collect_prior_artifacts(ctx)):
        if artifact.kind not in DATASET_ARTIFACT_TYPES:
            continue
        path = _resolve_local_artifact_path(artifact.uri)
        dataframe = _read_dataframe(path)
        return dataframe, artifact
    raise RuntimeError("No readable dataset artifact is available for this node")


def _collect_prior_artifacts(ctx: NodeExecutionContext) -> list[Artifact]:
    artifact_ids = _run_input_artifact_ids(ctx.run)
    prior_nodes = ctx.db.execute(
        select(WorkflowNodeExecution)
        .where(
            WorkflowNodeExecution.workflow_run_id == ctx.run.id,
            WorkflowNodeExecution.execution_index < ctx.node.execution_index,
        )
        .order_by(WorkflowNodeExecution.execution_index.asc())
    ).scalars()
    for node in prior_nodes:
        artifact_ids.extend(
            json.loads(node.produced_artifact_ids_json) if node.produced_artifact_ids_json else []
        )

    artifacts: list[Artifact] = []
    seen: set[uuid.UUID] = set()
    for artifact_id in artifact_ids:
        try:
            parsed_id = uuid.UUID(str(artifact_id))
        except ValueError:
            continue
        if parsed_id in seen:
            continue
        artifact = ctx.db.get(Artifact, parsed_id)
        if (
            artifact
            and artifact.workspace_id == ctx.run.workspace_id
            and artifact.tenant_id == ctx.run.tenant_id
        ):
            artifacts.append(artifact)
            seen.add(parsed_id)
    return artifacts


def _collect_prior_artifact_payloads(
    ctx: NodeExecutionContext, *, kinds: set[str] | None = None
) -> dict[str, Any]:
    payloads: dict[str, Any] = {}
    for artifact in _collect_prior_artifacts(ctx):
        if kinds and artifact.kind not in kinds:
            continue
        payloads[str(artifact.id)] = {
            "artifact_type": artifact.kind,
            "uri": artifact.uri,
            "payload": _read_artifact_payload(artifact),
        }
    if kinds == {"model"}:
        merged: dict[str, Any] = {}
        for item in payloads.values():
            if isinstance(item.get("payload"), dict):
                merged.update(item["payload"])
        return merged
    return payloads


def _read_artifact_payload(artifact: Artifact) -> Any:
    try:
        path = _resolve_local_artifact_path(artifact.uri)
    except RuntimeError:
        return {"uri": artifact.uri}
    suffix = path.suffix.lower()
    if suffix in {".json", ".jsonl"}:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {"uri": artifact.uri}
    if suffix in {".md", ".txt", ".html"}:
        return path.read_text(encoding="utf-8", errors="replace")[:20000]
    if _looks_like_tabular_uri(artifact.uri):
        return _dataframe_preview(_read_dataframe(path), rows=20)
    return {"uri": artifact.uri}


def _looks_like_tabular_uri(uri: str) -> bool:
    return Path(uri).suffix.lower() in {".csv", ".parquet", ".json", ".jsonl", ".xlsx", ".xls"}


def _resolve_local_artifact_path(uri: str) -> Path:
    if uri.startswith(("http://", "https://", "s3://", "gs://", "az://")):
        raise RuntimeError(
            f"Remote artifact reads are not available in this worker runtime yet: {uri}"
        )
    allowed_roots = [
        Path(settings.artifact_storage_local_dir).resolve(),
        Path(settings.chat_upload_dir).resolve(),
    ]
    raw = Path(uri)
    candidates = (
        [raw]
        if raw.is_absolute()
        else [
            Path(settings.artifact_storage_local_dir) / raw,
            Path(settings.chat_upload_dir) / raw,
            raw,
        ]
    )
    for candidate in candidates:
        resolved = candidate.resolve()
        if not any(resolved.is_relative_to(root) for root in allowed_roots):
            continue
        if resolved.exists() and resolved.is_file():
            return resolved
    raise RuntimeError(f"Artifact file does not exist in an allowed artifact directory: {uri}")


def _read_dataframe(path: Path) -> Any:
    import pandas as pd

    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if suffix in {".json", ".jsonl"}:
        return pd.read_json(path, lines=suffix == ".jsonl")
    raise RuntimeError(f"Unsupported dataset artifact file type: {suffix or '<none>'}")


def _build_dataframe_profile(dataframe: Any, *, sample_rows: int) -> dict[str, Any]:
    import pandas as pd

    numeric = dataframe.select_dtypes(include="number")
    sample = dataframe.head(max(0, sample_rows))
    profile = {
        "row_count": len(dataframe),
        "column_count": len(dataframe.columns),
        "columns": [
            {
                "name": str(column),
                "dtype": str(dataframe[column].dtype),
                "missing_count": int(dataframe[column].isna().sum()),
                "missing_ratio": float(dataframe[column].isna().mean()),
                "unique_count": int(dataframe[column].nunique(dropna=True)),
            }
            for column in dataframe.columns
        ],
        "numeric_summary": numeric.describe().to_dict() if not numeric.empty else {},
        "sample": sample.where(pd.notna(sample), None).to_dict(orient="records"),
    }
    return _json_safe(profile)


def _dataframe_preview(dataframe: Any, *, rows: int) -> dict[str, Any]:
    import pandas as pd

    preview = dataframe.head(max(0, rows)).where(pd.notna(dataframe.head(max(0, rows))), None)
    return {
        "rows": len(dataframe),
        "columns": list(map(str, dataframe.columns)),
        "sample": _json_safe(preview.to_dict(orient="records")),
    }


def _write_dataframe_artifact(ctx: NodeExecutionContext, *, filename: str, dataframe: Any) -> str:
    body = dataframe.to_csv(index=False).encode("utf-8")
    return _write_bytes_artifact(ctx, filename=filename, body=body, content_type="text/csv")


def _write_json_artifact(ctx: NodeExecutionContext, *, filename: str, payload: Any) -> str:
    body = json.dumps(_json_safe(payload), indent=2, sort_keys=True).encode("utf-8")
    return _write_bytes_artifact(ctx, filename=filename, body=body, content_type="application/json")


def _write_text_artifact(ctx: NodeExecutionContext, *, filename: str, content: str) -> str:
    return _write_bytes_artifact(
        ctx, filename=filename, body=content.encode("utf-8"), content_type="text/markdown"
    )


def _write_bytes_artifact(
    ctx: NodeExecutionContext, *, filename: str, body: bytes, content_type: str
) -> str:
    storage = get_artifact_storage_backend()
    key = f"workflow-runs/{ctx.run.id}/{ctx.node.node_id}/{filename}"
    if storage.backend == "local":
        path = Path(storage.root) / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return str(path.as_posix())
    if storage.backend == "s3":
        import boto3

        boto3.client("s3").put_object(
            Bucket=storage.root, Key=key, Body=body, ContentType=content_type
        )
        return storage.build_uri(key)
    if storage.backend == "gcs":
        from google.cloud import storage as gcs_storage

        bucket = gcs_storage.Client().bucket(storage.root)
        bucket.blob(key).upload_from_string(body, content_type=content_type)
        return storage.build_uri(key)
    raise RuntimeError(f"Unsupported artifact storage backend: {storage.backend}")


def _local_node_directory(ctx: NodeExecutionContext) -> Path:
    path = (
        Path(settings.artifact_storage_local_dir)
        / "workflow-runs"
        / str(ctx.run.id)
        / ctx.node.node_id
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except Exception:
            pass
    return str(value)
