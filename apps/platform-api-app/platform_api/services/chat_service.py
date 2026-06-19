from __future__ import annotations

import asyncio
import functools
import json
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, AsyncIterator

from prometheus_client import Counter, Gauge, Histogram
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from platform_api.core.config import settings
from platform_api.core.file_security import (
    secure_upload_directory,
    sanitize_svg_content,
    validate_upload,
    validate_zip_archive,
)
from platform_api.core.malware_scan import enforce_scan_mode
from platform_api.db.models import ChatMessage, ChatMessageRole, ChatSession, ChatSessionStatus, ChatUpload
from platform_api.core.service_errors import NotFoundError, ValidationError
from platform_api.control_plane.actions import plan_action_from_text
from platform_api.control_plane.query import build_context_for_chat_session, chat_platform_reply
from platform_api.services.workflow_chain_validator import inspect_workflow_spec

logger = logging.getLogger(__name__)

CHAT_STREAM_EVENTS_TOTAL = Counter(
    "platform_api_chat_stream_events_total",
    "Total number of chat stream events emitted",
    ["type"],
    registry=None,
)
CHAT_STREAM_DURATION = Histogram(
    "platform_api_chat_stream_duration_seconds",
    "Duration of streamed chat assistant generation",
    registry=None,
)
CHAT_BLOCKING_TASKS_IN_FLIGHT = Gauge(
    "platform_api_chat_blocking_tasks_in_flight",
    "Blocking chat tasks currently running in the bounded worker pool",
    registry=None,
)

_CHAT_EXECUTOR = ThreadPoolExecutor(
    max_workers=max(1, settings.chat_worker_max_threads),
    thread_name_prefix="platform-chat",
)

WORKFLOW_KEYWORDS = (
    "workflow",
    "pipeline",
    "orchestr",
    "schedule",
    "agent",
    "approval",
    "automation",
)


@dataclass(frozen=True)
class ChatStreamEvent:
    type: str
    delta: str | None = None
    text: str | None = None
    artifacts: list[dict] | None = None
    error: str | None = None


def _parse_uuid(value: str, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise ValidationError(f"Invalid {label}") from exc


def create_chat_session(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str,
) -> ChatSession:
    session = ChatSession(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        user_id=user_id,
        title=(title or "New chat").strip()[:200] or "New chat",
        status=ChatSessionStatus.active,
    )
    db.add(session)
    db.flush()
    # Persist session creation immediately so later message failures do not
    # erase the conversation shell that callers already received.
    db.commit()
    db.refresh(session)
    return session


def _apply_timestamp_cursor(
    db: Session,
    *,
    query,
    cursor: str | None,
    cursor_stmt,
    id_column,
    order_column,
    descending: bool,
):
    if not cursor:
        return query
    try:
        cursor_uuid = uuid.UUID(cursor)
    except ValueError:
        return query

    cursor_row = db.execute(cursor_stmt.where(id_column == cursor_uuid)).one_or_none()
    if cursor_row is None:
        return query

    cursor_value = cursor_row[0]
    if descending:
        return query.where(
            or_(
                order_column < cursor_value,
                and_(order_column == cursor_value, id_column < cursor_uuid),
            )
        )
    return query.where(
        or_(
            order_column > cursor_value,
            and_(order_column == cursor_value, id_column > cursor_uuid),
        )
    )


def list_chat_sessions(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    cursor: str | None = None,
    limit: int = 20,
) -> list[ChatSession]:
    query = select(ChatSession).where(
        ChatSession.workspace_id == workspace_id,
        ChatSession.user_id == user_id,
    )
    query = _apply_timestamp_cursor(
        db,
        query=query,
        cursor=cursor,
        cursor_stmt=select(ChatSession.updated_at).where(
            ChatSession.workspace_id == workspace_id,
            ChatSession.user_id == user_id,
        ),
        id_column=ChatSession.id,
        order_column=ChatSession.updated_at,
        descending=True,
    )
    query = query.order_by(ChatSession.updated_at.desc(), ChatSession.id.desc()).limit(limit + 1)
    return list(db.execute(query).scalars())


def get_chat_session(
    db: Session,
    *,
    session_id: str,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> ChatSession:
    """Get a chat session by ID, ensuring it belongs to the specified workspace.

    Security: workspace_id filter is applied IN the query (not post-fetch)
    to prevent IDOR vulnerabilities. If user_id is provided, also validates
    that the session belongs to the requesting user (prevents horizontal escalation).
    """
    sid = _parse_uuid(session_id, "session_id")
    query = select(ChatSession).where(
        ChatSession.id == sid,
        ChatSession.workspace_id == workspace_id,
    )
    if user_id is not None:
        query = query.where(ChatSession.user_id == user_id)
    session = db.execute(query).scalar_one_or_none()
    if session is None:
        raise NotFoundError("Chat session not found")
    return session


def create_message(
    db: Session,
    *,
    session: ChatSession,
    role: ChatMessageRole,
    content: str,
    artifacts: list[dict] | None = None,
) -> ChatMessage:
    artifacts_payload = artifacts or []
    message = ChatMessage(
        session_id=session.id,
        role=role,
        content=content,
        artifacts_json=json.dumps(artifacts_payload) if artifacts_payload else None,
    )
    db.add(message)
    session.updated_at = datetime.now(UTC)
    db.add(session)
    db.flush()
    return message


def create_pending_message(
    db: Session,
    *,
    session: ChatSession,
    role: ChatMessageRole,
    content: str = "",
    artifacts: list[dict] | None = None,
) -> ChatMessage:
    """Create a pending message that will be updated after streaming.

    This ensures message durability - if the server crashes during streaming,
    the message record exists and can be recovered.

    Parameters
    ----------
    db : Session
        Database session.
    session : ChatSession
        Chat session.
    role : ChatMessageRole
        Message role (user/assistant).
    content : str
        Initial content (empty for assistant during streaming).
    artifacts : list[dict] | None
        Initial artifacts (updated after streaming).

    Returns
    -------
    ChatMessage
        The created pending message.
    """
    artifacts_payload = artifacts or []
    message = ChatMessage(
        session_id=session.id,
        role=role,
        content=content,
        artifacts_json=json.dumps(artifacts_payload) if artifacts_payload else None,
    )
    db.add(message)
    session.updated_at = datetime.now(UTC)
    db.add(session)
    db.flush()
    return message


def update_message(
    db: Session,
    *,
    message: ChatMessage,
    content: str,
    artifacts: list[dict] | None = None,
) -> ChatMessage:
    """Update a message after streaming completes.

    Parameters
    ----------
    db : Session
        Database session.
    message : ChatMessage
        Message to update.
    content : str
        Final content.
    artifacts : list[dict] | None
        Final artifacts.

    Returns
    -------
    ChatMessage
        The updated message.
    """
    message.content = content
    if artifacts is not None:
        message.artifacts_json = json.dumps(artifacts) if artifacts else None
    db.add(message)
    db.flush()
    return message


def list_messages(
    db: Session,
    *,
    session_id: uuid.UUID,
    cursor: str | None = None,
    limit: int = 50,
) -> list[ChatMessage]:
    query = select(ChatMessage).where(ChatMessage.session_id == session_id)
    query = _apply_timestamp_cursor(
        db,
        query=query,
        cursor=cursor,
        cursor_stmt=select(ChatMessage.created_at).where(ChatMessage.session_id == session_id),
        id_column=ChatMessage.id,
        order_column=ChatMessage.created_at,
        descending=False,
    )
    query = query.order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc()).limit(limit + 1)
    return list(db.execute(query).scalars())


def save_upload(
    db: Session,
    *,
    session: ChatSession,
    filename: str | None,
    content_type: str | None,
    file_bytes: bytes,
    created_by_user_id: uuid.UUID,
) -> ChatUpload:
    """Save an uploaded file to tenant-aware storage with comprehensive security.

    Security measures:
    - Extension allowlist validation
    - MIME type detection from magic bytes (not trusted header)
    - Filename sanitization and random UUID naming
    - ZIP bomb protection
    - SVG XSS sanitization
    - Tenant-isolated directory structure

    Files are stored in:
        {upload_dir}/{tenant_id}/{workspace_id}/{session_id}/{uuid}.{ext}

    This prevents:
    - Cross-tenant file access
    - Extension-based attacks (RCE)
    - Path traversal
    - Information disclosure from filenames

    Best practice reference: https://owasp.org/www-community/vulnerabilities/Unrestricted_File_Upload
    """
    secure_filename, validated_mime, original_name = validate_upload(
        filename=filename or "upload.bin",
        content_type=content_type,
        file_bytes=file_bytes,
        max_size_mb=settings.chat_upload_max_mb,
    )
    enforce_scan_mode(file_bytes, settings.malware_scan_mode)

    if validated_mime == 'application/zip':
        validate_zip_archive(file_bytes)

    file_content = file_bytes
    if secure_filename.lower().endswith('.svg'):
        file_content = sanitize_svg_content(file_bytes)

    base_upload_dir = Path(settings.chat_upload_dir).resolve()

    secure_upload_directory(base_upload_dir)

    tenant_dir = base_upload_dir / str(session.tenant_id)
    workspace_dir = tenant_dir / str(session.workspace_id)
    session_dir = workspace_dir / str(session.id)

    session_dir.mkdir(parents=True, exist_ok=True)

    file_path = session_dir / secure_filename

    temp_path = file_path.with_suffix(file_path.suffix + ".tmp")
    try:
        with temp_path.open("wb") as fp:
            fp.write(file_content)
        temp_path.rename(file_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise

    relative_path = Path(str(session.tenant_id)) / str(session.workspace_id) / str(session.id) / secure_filename
    storage_uri = str(relative_path)

    try:
        upload = ChatUpload(
            session_id=session.id,
            tenant_id=session.tenant_id,
            workspace_id=session.workspace_id,
            filename=original_name,
            content_type=validated_mime,
            size_bytes=len(file_bytes),
            storage_uri=storage_uri,
            created_by_user_id=created_by_user_id,
        )
        db.add(upload)
        db.flush()
    except Exception:
        if file_path.exists():
            file_path.unlink()
        raise

    return upload


def list_uploads(
    db: Session,
    *,
    session_id: uuid.UUID,
) -> list[ChatUpload]:
    return list(
        db.execute(
            select(ChatUpload)
            .where(ChatUpload.session_id == session_id)
            .order_by(ChatUpload.created_at.desc(), ChatUpload.id.desc())
        ).scalars()
    )


def _resolve_upload_path(upload: ChatUpload) -> Path:
    return Path(settings.chat_upload_dir).resolve() / upload.storage_uri


def _load_dataframe_from_upload(upload: ChatUpload) -> tuple[Any, str] | None:
    try:
        import pandas as pd
    except ImportError:
        logger.warning("pandas is not installed; skipping dataset-aware chat replies")
        return None

    path = _resolve_upload_path(upload)
    if not path.exists():
        return None

    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            return pd.read_csv(path), upload.filename
        if suffix in {".tsv", ".txt"}:
            return pd.read_csv(path, sep="\t"), upload.filename
        if suffix == ".json":
            return pd.read_json(path), upload.filename
        if suffix in {".xlsx", ".xls"}:
            return pd.read_excel(path), upload.filename
        if suffix == ".parquet":
            return pd.read_parquet(path), upload.filename
    except Exception as exc:
        logger.warning("Failed to parse upload %s as dataframe: %s", upload.filename, exc)
        return None

    return None


def _load_session_dataframe(db: Session, *, session: ChatSession) -> tuple[Any, str] | None:
    for upload in list_uploads(db, session_id=session.id):
        loaded = _load_dataframe_from_upload(upload)
        if loaded is not None:
            return loaded
    return None


async def _run_chat_blocking(func, /, *args, **kwargs):
    loop = asyncio.get_running_loop()
    call = functools.partial(func, *args, **kwargs)
    CHAT_BLOCKING_TASKS_IN_FLIGHT.inc()
    try:
        return await loop.run_in_executor(_CHAT_EXECUTOR, call)
    finally:
        CHAT_BLOCKING_TASKS_IN_FLIGHT.dec()


async def _load_session_dataframe_async(db: Session, *, session: ChatSession) -> tuple[Any, str] | None:
    for upload in list_uploads(db, session_id=session.id):
        loaded = await _run_chat_blocking(_load_dataframe_from_upload, upload)
        if loaded is not None:
            return loaded
    return None


def _build_upload_summary(uploads: list[ChatUpload]) -> str:
    if not uploads:
        return "No uploads are attached to this chat yet."
    names = ", ".join(upload.filename for upload in uploads[:3])
    extra = len(uploads) - 3
    if extra > 0:
        names = f"{names}, +{extra} more"
    return f"Attached uploads: {names}."


def _select_modeling_agent(lower_prompt: str) -> str:
    if "anomaly" in lower_prompt:
        return "Anomaly Detection"
    if any(keyword in lower_prompt for keyword in ("forecast", "time series", "timeseries")):
        return "Forecasting Model"
    if any(keyword in lower_prompt for keyword in ("cluster", "segmentation")):
        return "Clustering"
    return "H2O ML"


def _build_workflow_design(prompt: str, uploads: list[ChatUpload], dataframe: Any | None) -> tuple[str, list[dict]]:
    lower = prompt.lower()
    include_modeling = any(
        keyword in lower
        for keyword in ("forecast", "predict", "classification", "cluster", "anomaly", "model")
    )
    modeling_agent = _select_modeling_agent(lower)

    first_step = {
        "id": "profile_data",
        "agent": "EDA",
        "instruction": "Profile the attached dataset, inspect schema, and identify quality risks.",
    }
    if uploads:
        first_step["instruction"] = (
            f"Profile the attached dataset(s) starting with {uploads[0].filename}, inspect schema, "
            "and identify quality risks."
        )

    steps = [
        first_step,
        {
            "id": "clean_data",
            "agent": "Data Cleaning",
            "instruction": "Fix missing values, normalize column types, and document transformations.",
            "depends_on": ["profile_data"],
        },
    ]

    summary_depends_on = ["clean_data"]

    if modeling_agent == "Forecasting Model":
        steps.append(
            {
                "id": "time_series_eda",
                "agent": "Time Series EDA",
                "instruction": "Validate date grain, seasonality, missing timestamps, and forecastability before modeling.",
                "depends_on": ["clean_data"],
            }
        )
        summary_depends_on = ["time_series_eda"]

    if include_modeling:
        steps.append(
            {
                "id": "train_model",
                "agent": modeling_agent,
                "instruction": "Run modeling or forecasting based on the user's goal and compare candidate approaches.",
                "depends_on": summary_depends_on,
            }
        )
        summary_depends_on = ["train_model"]

    steps.append(
        {
            "id": "narrative_report",
            "agent": "Narrative",
            "instruction": "Produce an executive summary with findings, risks, and recommended next actions.",
            "depends_on": summary_depends_on,
        }
    )

    schedule: dict[str, str] | None = None
    if "daily" in lower:
        schedule = {"cron": "0 8 * * *", "natural_language": "Daily at 08:00", "timezone": "UTC"}
    elif "weekly" in lower:
        schedule = {"cron": "0 8 * * 1", "natural_language": "Every Monday at 08:00", "timezone": "UTC"}

    workflow_spec: dict[str, Any] = {
        "name": "AI Workspace Workflow",
        "description": prompt.strip() or "Orchestrated workflow proposed from chat.",
        "steps": steps,
        "hitl_config": {
            "approval_gates": ["narrative_report"],
            "confidence_threshold": 0.8,
        },
    }
    if schedule:
        workflow_spec["schedule"] = schedule

    validation = inspect_workflow_spec(workflow_spec)
    if validation["errors"]:
        logger.warning(
            "Generated workflow design failed validation for prompt %r: %s",
            prompt,
            "; ".join(issue["message"] for issue in validation["errors"]),
        )

    text = (
        "I converted your request into an execution-ready workflow draft. "
        "Review the proposed steps, approve it to save and trigger a run, or request modifications."
    )
    if dataframe is not None:
        text += " The draft is grounded in the uploaded tabular dataset."
    elif uploads:
        text += f" {_build_upload_summary(uploads)}"
    if validation["warnings"]:
        text += " Some edges are advisory and may need user review before production use."
    return text, [{"type": "workflow_design", "workflow_spec": workflow_spec}]


def _normalize_chatworkspace_artifact(artifact_type: str | None, artifact_data: dict | None) -> list[dict]:
    if not artifact_type or not artifact_data:
        return []
    if artifact_type == "table":
        records = artifact_data.get("records", [])
        try:
            records = json.loads(json.dumps(records, default=str))
        except TypeError:
            records = []
        return [
            {
                "type": "table",
                "columns": artifact_data.get("columns", []),
                "records": records,
            }
        ]
    if artifact_type == "code":
        return [
            {
                "type": "code",
                "language": artifact_data.get("language", "python"),
                "code": artifact_data.get("code", ""),
            }
        ]
    if artifact_type == "chart":
        traces = artifact_data.get("data", []) if isinstance(artifact_data, dict) else []
        categories = None
        series = []
        if traces:
            for trace in traces[:3]:
                x_vals = trace.get("x") or trace.get("labels") or []
                y_vals = trace.get("y") or trace.get("values") or []
                if categories is None and x_vals:
                    categories = [str(value) for value in list(x_vals)[:12]]
                if y_vals:
                    numeric_points = []
                    for value in list(y_vals)[:12]:
                        try:
                            numeric_points.append(float(value))
                        except (TypeError, ValueError):
                            numeric_points.append(0.0)
                    series.append({"name": trace.get("name", "metric"), "data": numeric_points})
        if series:
            return [
                {
                    "type": "chart",
                    "chart_type": "line",
                    "categories": categories or [f"P{i + 1}" for i in range(len(series[0]["data"]))],
                    "series": series,
                    "meta": {"title": "AI Workspace Chart"},
                }
            ]
    return []


def _get_chatworkspace_session_store():
    if settings.agent_cache_redis_url:
        try:
            from ai_data_science_team.redis_stores import RedisChatSessionStore
            return RedisChatSessionStore(redis_url=settings.agent_cache_redis_url)
        except Exception as exc:
            logger.info("RedisChatSessionStore unavailable, using in-memory fallback: %s", exc)
    return None


def _try_chatworkspace_reply(
    *,
    prompt: str,
    dataframe: Any | None,
) -> tuple[str, list[dict]] | None:
    if dataframe is None or not settings.openai_api_key:
        return None

    try:
        from langchain_openai import ChatOpenAI
        from ai_data_science_team.multiagents.chat_workspace import ChatWorkspace
    except ImportError as exc:
        logger.info("ChatWorkspace dependencies unavailable, using fallback reply path: %s", exc)
        return None

    try:
        workspace = ChatWorkspace(
            model=ChatOpenAI(model=settings.openai_model, temperature=0),
            session_store=_get_chatworkspace_session_store(),
        )
        runtime_session_id = workspace.create_session()
        workspace.upload_dataset(runtime_session_id, "uploaded_dataset", dataframe)
        response = workspace.chat(runtime_session_id, prompt)
        return response.text, _normalize_chatworkspace_artifact(
            response.artifact_type,
            response.artifact_data,
        )
    except Exception as exc:
        logger.warning("ChatWorkspace execution failed, using fallback reply path: %s", exc)
        return None


async def _try_chatworkspace_reply_stream(
    *,
    prompt: str,
    dataframe: Any | None,
) -> AsyncIterator[ChatStreamEvent]:
    if dataframe is None or not settings.openai_api_key:
        return

    try:
        from langchain_openai import ChatOpenAI
        from ai_data_science_team.multiagents.chat_workspace import ChatWorkspace
    except ImportError as exc:
        logger.info("ChatWorkspace dependencies unavailable, using fallback reply path: %s", exc)
        return

    try:
        workspace = ChatWorkspace(
            model=ChatOpenAI(model=settings.openai_model, temperature=0, streaming=True),
            session_store=_get_chatworkspace_session_store(),
        )
        runtime_session_id = workspace.create_session()
        workspace.upload_dataset(runtime_session_id, "uploaded_dataset", dataframe)
        async for event in workspace.astream(runtime_session_id, prompt):
            if event.type == "progress":
                yield ChatStreamEvent(type="progress")
            elif event.type == "response" and event.response is not None:
                artifacts = _normalize_chatworkspace_artifact(
                    event.response.artifact_type,
                    event.response.artifact_data,
                )
                yield ChatStreamEvent(
                    type="final",
                    delta=event.response.text,
                    text=event.response.text,
                    artifacts=artifacts
                    or [{"type": "report", "title": "AI Workspace Response", "content": event.response.text}],
                )
    except Exception as exc:
        logger.warning("ChatWorkspace streaming failed, using fallback reply path: %s", exc)


def build_assistant_reply(
    prompt: str,
    *,
    uploads: list[ChatUpload] | None = None,
    dataframe: Any | None = None,
    dataset_name: str | None = None,
) -> tuple[str, list[dict]]:
    text = (prompt or "").strip()
    lower = text.lower()
    uploads = uploads or []

    if any(keyword in lower for keyword in WORKFLOW_KEYWORDS):
        return _build_workflow_design(text, uploads, dataframe)

    artifacts: list[dict] = []
    dataframe_preview = None
    numeric_columns: list[str] = []
    if dataframe is not None:
        try:
            dataframe_preview = dataframe.head(8)
            numeric_columns = list(dataframe_preview.select_dtypes(include="number").columns)
        except Exception:
            dataframe_preview = None
            numeric_columns = []

    if any(k in lower for k in ["chart", "grafik", "trend"]):
        if dataframe_preview is not None and numeric_columns:
            chart_points = list(dataframe_preview[numeric_columns[0]].fillna(0).astype(float).head(8))
            categories = [str(i + 1) for i in range(len(chart_points))]
            artifacts.append(
                {
                    "type": "chart",
                    "chart_type": "line",
                    "meta": {"title": f"{numeric_columns[0]} trend"},
                    "series": [{"name": numeric_columns[0], "data": chart_points}],
                    "categories": categories,
                }
            )
        else:
            artifacts.append(
                {
                    "type": "chart",
                    "chart_type": "line",
                    "meta": {"title": "Trend Overview"},
                    "series": [{"name": "metric", "data": [12, 19, 15, 24, 22]}],
                    "categories": ["P1", "P2", "P3", "P4", "P5"],
                }
            )
    if any(k in lower for k in ["table", "tablo", "list"]):
        if dataframe_preview is not None:
            artifacts.append(
                {
                    "type": "table",
                    "columns": [str(column) for column in dataframe_preview.columns],
                    "records": json.loads(dataframe_preview.to_json(orient="records")),
                }
            )
        else:
            artifacts.append(
                {
                    "type": "table",
                    "columns": ["segment", "value"],
                    "records": [
                        {"segment": "A", "value": 42},
                        {"segment": "B", "value": 31},
                    ],
                }
            )
    if any(k in lower for k in ["code", "python", "sql"]):
        dataset_reference = dataset_name or (uploads[0].filename if uploads else "uploaded_dataset.csv")
        artifacts.append(
            {
                "type": "code",
                "language": "python",
                "code": (
                    "import pandas as pd\n\n"
                    f"df = pd.read_csv('{dataset_reference}')\n"
                    "summary = df.describe(include='all').transpose()\n"
                    "print(summary.head())\n"
                ),
            }
        )
    if any(k in lower for k in ["report", "ozet", "summary"]):
        artifacts.append(
            {
                "type": "report",
                "title": "Executive Summary",
                "content": (
                    "Top findings and action recommendations were generated.\n\n"
                    f"{_build_upload_summary(uploads)}"
                ),
            }
        )

    if not artifacts:
        artifacts.append(
            {
                "type": "report",
                "title": "Assistant Response",
                "content": (
                    "No structured artifact requested, returning concise analysis notes.\n\n"
                    f"{_build_upload_summary(uploads)}"
                ),
            }
        )

    response = (
        "I analyzed your request and produced structured artifacts from the current chat context. "
        "You can inspect chart, table, code, report, or workflow cards in the workspace panel."
    )
    if dataset_name:
        response += f" Active dataset: {dataset_name}."
    return response, artifacts


def generate_assistant_reply(
    db: Session,
    *,
    session: ChatSession,
    prompt: str,
) -> tuple[str, list[dict]]:
    platform_reply = _try_platform_control_reply(db, session=session, prompt=prompt)
    if platform_reply is not None:
        return platform_reply

    uploads = list_uploads(db, session_id=session.id)
    loaded_dataframe = _load_session_dataframe(db, session=session)
    dataframe = loaded_dataframe[0] if loaded_dataframe is not None else None
    dataset_name = loaded_dataframe[1] if loaded_dataframe is not None else None

    chatworkspace_reply = _try_chatworkspace_reply(prompt=prompt, dataframe=dataframe)
    if chatworkspace_reply is not None:
        text, artifacts = chatworkspace_reply
        if artifacts:
            return text, artifacts
        return text, [
            {
                "type": "report",
                "title": "AI Workspace Response",
                "content": text,
            }
        ]

    return build_assistant_reply(
        prompt,
        uploads=uploads,
        dataframe=dataframe,
        dataset_name=dataset_name,
    )


async def stream_assistant_reply(
    db: Session,
    *,
    session: ChatSession,
    prompt: str,
) -> AsyncIterator[ChatStreamEvent]:
    start = perf_counter()
    try:
        CHAT_STREAM_EVENTS_TOTAL.labels(type="progress").inc()
        yield ChatStreamEvent(type="progress")

        platform_reply = _try_platform_control_reply(db, session=session, prompt=prompt)
        if platform_reply is not None:
            text, artifacts = platform_reply
            CHAT_STREAM_EVENTS_TOTAL.labels(type="final").inc()
            yield ChatStreamEvent(type="final", delta=text, text=text, artifacts=artifacts)
            return

        uploads = list_uploads(db, session_id=session.id)
        loaded_dataframe = await _load_session_dataframe_async(db, session=session)
        dataframe = loaded_dataframe[0] if loaded_dataframe is not None else None
        dataset_name = loaded_dataframe[1] if loaded_dataframe is not None else None

        async for event in _try_chatworkspace_reply_stream(prompt=prompt, dataframe=dataframe):
            CHAT_STREAM_EVENTS_TOTAL.labels(type=event.type).inc()
            yield event
            if event.type == "final":
                return

        text, artifacts = await _run_chat_blocking(
            build_assistant_reply,
            prompt,
            uploads=uploads,
            dataframe=dataframe,
            dataset_name=dataset_name,
        )
        CHAT_STREAM_EVENTS_TOTAL.labels(type="final").inc()
        yield ChatStreamEvent(type="final", delta=text, text=text, artifacts=artifacts)
    except Exception as exc:
        CHAT_STREAM_EVENTS_TOTAL.labels(type="error").inc()
        yield ChatStreamEvent(type="error", error=str(exc))
    finally:
        CHAT_STREAM_DURATION.observe(perf_counter() - start)


def _try_platform_control_reply(
    db: Session,
    *,
    session: ChatSession,
    prompt: str,
) -> tuple[str, list[dict]] | None:
    ctx = build_context_for_chat_session(db, session)
    if ctx is None:
        return None
    action_plan = plan_action_from_text(prompt)
    return chat_platform_reply(ctx, prompt, action_plan=action_plan)


def message_to_dict(message: ChatMessage) -> dict:
    artifacts = []
    if message.artifacts_json:
        try:
            artifacts = json.loads(message.artifacts_json)
        except json.JSONDecodeError as e:
            logger.warning(
                "Failed to parse artifacts JSON for message %s: %s",
                message.id, e,
            )
            artifacts = []
    return {
        "id": str(message.id),
        "session_id": str(message.session_id),
        "role": message.role.value if hasattr(message.role, "value") else str(message.role),
        "content": message.content,
        "artifacts": artifacts,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


def session_to_dict(session: ChatSession) -> dict:
    return {
        "id": str(session.id),
        "tenant_id": str(session.tenant_id),
        "workspace_id": str(session.workspace_id),
        "user_id": str(session.user_id),
        "title": session.title,
        "status": session.status.value if hasattr(session.status, "value") else str(session.status),
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
    }


def upload_to_dict(upload: ChatUpload) -> dict:
    return {
        "id": str(upload.id),
        "session_id": str(upload.session_id),
        "filename": upload.filename,
        "content_type": upload.content_type,
        "size_bytes": upload.size_bytes,
        "storage_uri": upload.storage_uri,
        "created_at": upload.created_at.isoformat() if upload.created_at else None,
    }
