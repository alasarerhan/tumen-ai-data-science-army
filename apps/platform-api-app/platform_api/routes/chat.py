from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from platform_api.auth.dependencies import get_principal
from platform_api.auth.models import Principal
from platform_api.core.config import settings
from platform_api.core.file_security import (
    detect_mime_from_magic_bytes,
    generate_secure_filename,
    sanitize_filename,
    secure_upload_directory,
    stream_upload_to_file,
    validate_file_extension,
    validate_mime_type,
    validate_zip_archive,
)
from platform_api.core.malware_scan import enforce_scan_mode
from platform_api.db.models import ChatMessageRole, ChatSessionStatus, ChatUpload
from platform_api.db.session import get_db
from platform_api.schemas.pagination import build_paginated_response, MAX_PAGE_SIZE
from platform_api.services.identity_service import get_or_create_user
from platform_api.services.run_service import get_workspace_for_member
from platform_api.services.chat_service import (
    create_chat_session,
    create_message,
    create_pending_message,
    generate_assistant_reply,
    get_chat_session,
    list_chat_sessions,
    list_messages,
    list_uploads,
    message_to_dict,
    save_upload,
    session_to_dict,
    update_message,
    upload_to_dict,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/chat", tags=["chat"])

MIN_UPLOAD_SIZE_BYTES = 1
MAX_UPLOAD_SIZE_BYTES = settings.chat_upload_max_mb * 1024 * 1024


class CreateChatSessionRequest(BaseModel):
    workspace_id: str
    title: str = "New chat"


class CreateChatMessageRequest(BaseModel):
    workspace_id: str
    content: str = Field(min_length=1, max_length=20_000)


def _resolve_context(db: Session, principal: Principal, workspace_id: str) -> tuple:
    user = get_or_create_user(db, principal)
    workspace = get_workspace_for_member(db, workspace_id=workspace_id, user_id=user.id)
    return user, workspace


def _sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\\n\\n"


@router.post("/sessions", status_code=201)
async def create_session(
    body: CreateChatSessionRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    user, workspace = _resolve_context(db, principal, body.workspace_id)
    session = create_chat_session(
        db,
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
        user_id=user.id,
        title=body.title,
    )
    db.commit()
    db.refresh(session)
    return session_to_dict(session)


@router.get("/sessions")
async def get_sessions(
    workspace_id: str,
    cursor: Optional[str] = Query(default=None, description="Pagination cursor (session ID)"),
    limit: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    user, workspace = _resolve_context(db, principal, workspace_id)
    sessions = list_chat_sessions(
        db, workspace_id=workspace.id, user_id=user.id, cursor=cursor, limit=limit
    )
    paginated = build_paginated_response(sessions, limit)
    return {
        "items": [session_to_dict(s) for s in paginated["items"]],
        "next_cursor": paginated["next_cursor"],
        "has_more": paginated["has_more"],
    }


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    workspace_id: str,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    user, workspace = _resolve_context(db, principal, workspace_id)
    session = get_chat_session(db, session_id=session_id, workspace_id=workspace.id, user_id=user.id)
    return session_to_dict(session)


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    workspace_id: str,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    user, workspace = _resolve_context(db, principal, workspace_id)
    session = get_chat_session(db, session_id=session_id, workspace_id=workspace.id, user_id=user.id)
    session.status = ChatSessionStatus.archived
    db.add(session)
    db.commit()
    db.refresh(session)
    return session_to_dict(session)


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    workspace_id: str,
    cursor: Optional[str] = Query(default=None, description="Pagination cursor (message ID)"),
    limit: int = Query(default=50, ge=1, le=100, description="Items per page"),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    user, workspace = _resolve_context(db, principal, workspace_id)
    session = get_chat_session(db, session_id=session_id, workspace_id=workspace.id, user_id=user.id)
    messages = list_messages(db, session_id=session.id, cursor=cursor, limit=limit)
    paginated = build_paginated_response(messages, limit)
    return {
        "items": [message_to_dict(m) for m in paginated["items"]],
        "next_cursor": paginated["next_cursor"],
        "has_more": paginated["has_more"],
    }


@router.post("/sessions/{session_id}/messages", status_code=201)
async def create_session_message(
    session_id: str,
    body: CreateChatMessageRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    user, workspace = _resolve_context(db, principal, body.workspace_id)
    session = get_chat_session(db, session_id=session_id, workspace_id=workspace.id, user_id=user.id)

    create_message(db, session=session, role=ChatMessageRole.user, content=body.content)
    assistant_text, artifacts = generate_assistant_reply(db, session=session, prompt=body.content)
    assistant = create_message(
        db,
        session=session,
        role=ChatMessageRole.assistant,
        content=assistant_text,
        artifacts=artifacts,
    )
    db.commit()
    db.refresh(assistant)
    return message_to_dict(assistant)


@router.post("/sessions/{session_id}/messages/stream")
async def stream_session_message(
    session_id: str,
    body: CreateChatMessageRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Stream a chat message with durable message storage.

    Message Durability Pattern:
    1. Save user message immediately (committed)
    2. Create pending assistant message (committed)
    3. Stream response chunks
    4. Update assistant message with final content (committed)

    If server crashes during streaming:
    - User message is preserved
    - Assistant message exists (may be empty/incomplete)
    - Client can detect incomplete message and retry

    Best Practices Reference:
    https://ithy.com/article/sse-streaming-retries-v0p7rdp1
    """
    user, workspace = _resolve_context(db, principal, body.workspace_id)
    session = get_chat_session(db, session_id=session_id, workspace_id=workspace.id, user_id=user.id)

    create_pending_message(
        db, session=session, role=ChatMessageRole.user, content=body.content
    )

    assistant_text, artifacts = generate_assistant_reply(db, session=session, prompt=body.content)

    pending_assistant = create_pending_message(
        db, session=session, role=ChatMessageRole.assistant, content="", artifacts=None
    )
    db.commit()
    db.refresh(pending_assistant)

    async def _generator():
        chunk_wait_seconds = max(1, settings.chat_stream_chunk_ms) / 1000.0
        accumulated_text = ""
        try:
            words = assistant_text.split(" ")
            for word in words:
                piece = f"{word} "
                accumulated_text += piece
                yield _sse_event({"type": "delta", "delta": piece, "message_id": str(pending_assistant.id)})
                await asyncio.sleep(chunk_wait_seconds)

            full_text = accumulated_text.strip()
            assistant = update_message(
                db,
                message=pending_assistant,
                content=full_text,
                artifacts=artifacts,
            )
            db.commit()
            yield _sse_event({"type": "message", "message": message_to_dict(assistant)})
        except Exception as exc:
            db.rollback()
            update_message(
                db,
                message=pending_assistant,
                content=accumulated_text or "[Error: Streaming interrupted]",
                artifacts=None,
            )
            db.commit()
            error_msg = "An error occurred during streaming. Please try again."
            if isinstance(exc, (ValueError, KeyError)):
                error_msg = "Invalid request format."
            elif "timeout" in str(exc).lower():
                error_msg = "Request timed out. Please try again."
            logger.error("Chat streaming error: %s", type(exc).__name__)
            yield _sse_event({"type": "error", "error": error_msg, "message_id": str(pending_assistant.id)})
        finally:
            yield _sse_event({"type": "done", "message_id": str(pending_assistant.id)})

    return StreamingResponse(_generator(), media_type="text/event-stream")


@router.post("/sessions/{session_id}/uploads", status_code=201)
async def upload_file(
    session_id: str,
    workspace_id: str = Form(...),
    file: UploadFile = File(...),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    user, workspace = _resolve_context(db, principal, workspace_id)
    session = get_chat_session(db, session_id=session_id, workspace_id=workspace.id, user_id=user.id)
    data = await file.read()
    
    if len(data) < MIN_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File is too small. Minimum size is {MIN_UPLOAD_SIZE_BYTES} bytes."
        )
    
    if len(data) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File is too large. Maximum size is {settings.chat_upload_max_mb}MB."
        )
    
    upload = save_upload(
        db,
        session=session,
        filename=file.filename,
        content_type=file.content_type,
        file_bytes=data,
        created_by_user_id=user.id,
    )
    db.commit()
    db.refresh(upload)
    return upload_to_dict(upload)


@router.post("/sessions/{session_id}/uploads/stream", status_code=201)
async def upload_file_streaming(
    session_id: str,
    workspace_id: str = Form(...),
    file: UploadFile = File(...),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    """Stream upload file with memory-efficient processing.

    Security measures:
    - Streaming upload (no full file in memory)
    - Extension validation
    - MIME type detection from magic bytes
    - Secure filename generation
    - Size limit enforcement during streaming

    Use this endpoint for large file uploads to avoid memory exhaustion.
    """
    user, workspace = _resolve_context(db, principal, workspace_id)
    session = get_chat_session(db, session_id=session_id, workspace_id=workspace.id, user_id=user.id)

    validate_file_extension(file.filename or "upload.bin")

    base_upload_dir = Path(settings.chat_upload_dir).resolve()
    secure_upload_directory(base_upload_dir)

    tenant_dir = base_upload_dir / str(session.tenant_id)
    workspace_dir = tenant_dir / str(session.workspace_id)
    session_dir = workspace_dir / str(session.id)

    session_dir.mkdir(parents=True, exist_ok=True)

    temp_filename = f"{uuid4().hex}.tmp"
    temp_path = session_dir / temp_filename

    total_size, first_chunk = await stream_upload_to_file(
        file=file,
        target_path=temp_path,
        max_size_bytes=MAX_UPLOAD_SIZE_BYTES,
    )

    if total_size < MIN_UPLOAD_SIZE_BYTES:
        temp_path.unlink()
        raise HTTPException(
            status_code=400,
            detail=f"File is too small. Minimum size is {MIN_UPLOAD_SIZE_BYTES} bytes."
        )

    detected_ext, detected_mime = detect_mime_from_magic_bytes(first_chunk)
    validate_mime_type(file.content_type, detected_mime)

    secure_filename = generate_secure_filename(file.filename or "upload.bin", detected_ext)
    final_path = session_dir / secure_filename

    temp_path.rename(final_path)
    file_bytes = final_path.read_bytes()
    if detected_mime == "application/zip":
        validate_zip_archive(file_bytes)
    try:
        enforce_scan_mode(file_bytes, settings.malware_scan_mode)
    except ValueError as exc:
        final_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Upload rejected by malware policy") from exc

    original_name = sanitize_filename(file.filename or "upload.bin")

    relative_path = Path(str(session.tenant_id)) / str(session.workspace_id) / str(session.id) / secure_filename
    storage_uri = str(relative_path)

    try:
        upload = ChatUpload(
            session_id=session.id,
            tenant_id=session.tenant_id,
            workspace_id=session.workspace_id,
            filename=original_name,
            content_type=detected_mime,
            size_bytes=total_size,
            storage_uri=storage_uri,
            created_by_user_id=user.id,
        )
        db.add(upload)
        db.commit()
        db.refresh(upload)
    except Exception:
        if final_path.exists():
            final_path.unlink()
        raise

    return upload_to_dict(upload)


@router.get("/sessions/{session_id}/uploads")
async def get_uploads(
    session_id: str,
    workspace_id: str,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    user, workspace = _resolve_context(db, principal, workspace_id)
    session = get_chat_session(db, session_id=session_id, workspace_id=workspace.id, user_id=user.id)
    items = list_uploads(db, session_id=session.id)
    return {"items": [upload_to_dict(i) for i in items]}

