from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from platform_api.auth.dependencies import get_principal
from platform_api.auth.models import Principal
from platform_api.authz.dependencies import require_workspace_member
from platform_api.core.config import settings
from platform_api.core.file_security import (
    detect_mime_from_magic_bytes,
    get_content_disposition_header,
)
from platform_api.core.egress_policy import enforce_egress_policy
from platform_api.db.session import get_db
from platform_api.schemas.pagination import build_paginated_response, MAX_PAGE_SIZE
from platform_api.schemas.artifacts import CreateArtifactRequest
from platform_api.services.artifact_service import (
    create_artifact_record,
    get_artifact_for_workspace,
    list_artifacts_for_workspace,
)
from platform_api.services.identity_service import get_or_create_user

router = APIRouter(prefix="/v1/artifacts", tags=["artifacts"])


@router.post("")  # workspace_id in body — service-level membership check
async def create_artifact(
    payload: CreateArtifactRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    user = get_or_create_user(db, principal)
    artifact = create_artifact_record(
        db,
        workspace_id=payload.workspace_id,
        workflow_run_id=payload.workflow_run_id,
        kind=payload.kind,
        uri=payload.uri,
        user_id=user.id,
    )
    db.commit()
    return {
        "id": str(artifact.id),
        "tenant_id": str(artifact.tenant_id),
        "workspace_id": str(artifact.workspace_id),
        "workflow_run_id": str(artifact.workflow_run_id) if artifact.workflow_run_id else None,
        "kind": artifact.kind,
        "uri": artifact.uri,
    }


@router.get("")
async def list_artifacts(
    cursor: Optional[str] = Query(default=None, description="Pagination cursor (artifact ID)"),
    limit: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> dict:
    user = context["user"]
    workspace = context["workspace"]
    artifacts = list_artifacts_for_workspace(
        db, workspace_id=str(workspace.id), user_id=user.id, cursor=cursor, limit=limit
    )
    paginated = build_paginated_response(artifacts, limit)
    return {
        "items": [
            {
                "id": str(artifact.id),
                "kind": artifact.kind,
                "uri": artifact.uri,
                "workflow_run_id": str(artifact.workflow_run_id) if artifact.workflow_run_id else None,
                "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
            }
            for artifact in paginated["items"]
        ],
        "next_cursor": paginated["next_cursor"],
        "has_more": paginated["has_more"],
    }


@router.get("/{artifact_id}/access")  # workspace member required
async def get_artifact_access(
    artifact_id: str,
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> dict:
    user = context["user"]
    workspace = context["workspace"]
    artifact = get_artifact_for_workspace(
        db,
        artifact_id=artifact_id,
        workspace_id=str(workspace.id),
        user_id=user.id,
    )

    uri = artifact.uri

    # Determine delivery strategy based on URI scheme
    if uri.startswith(("https://", "http://")):
        try:
            enforce_egress_policy(
                url=uri,
                allowed_hosts=settings.artifact_redirect_allowed_hosts,
                strict_mode=settings.artifact_redirect_strict_mode,
                purpose="artifact_redirect",
            )
        except ValueError as exc:
            raise HTTPException(status_code=403, detail="Artifact redirect target is not allowed") from exc
        delivery = {"type": "redirect", "url": uri}
    elif uri.startswith("s3://"):
        delivery = {
            "type": "s3",
            "uri": uri,
            "note": "Generate a presigned URL via boto3.client('s3').generate_presigned_url()",
        }
    elif uri.startswith("gs://"):
        delivery = {
            "type": "gcs",
            "uri": uri,
            "note": "Generate a signed URL via google.cloud.storage Blob.generate_signed_url()",
        }
    elif uri.startswith("az://") or "blob.core.windows.net" in uri:
        delivery = {
            "type": "azure-blob",
            "uri": uri,
            "note": "Generate a SAS token via azure.storage.blob BlobClient.generate_sas()",
        }
    else:
        # Local/internal path — serve through the backend stream proxy
        delivery = {
            "type": "internal-stream",
            "url": f"/v1/artifacts/{artifact.id}/stream?workspace_id={workspace.id}",
        }

    return {
        "artifact_id": str(artifact.id),
        "kind": artifact.kind,
        "access_mode": "read-only",
        "delivery": delivery,
    }


@router.get("/{artifact_id}/stream")
async def stream_artifact(
    artifact_id: str,
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Stream artifact file content with security headers.

    Security measures:
    - Authorization check via require_workspace_member
    - Path traversal prevention
    - MIME type detection from file content (not filename)
    - X-Content-Type-Options: nosniff header
    - Content-Disposition for dangerous file types
    - No directory listing

    Returns the file with appropriate security headers.
    """
    from fastapi import HTTPException

    user = context["user"]
    workspace = context["workspace"]
    artifact = get_artifact_for_workspace(
        db,
        artifact_id=artifact_id,
        workspace_id=str(workspace.id),
        user_id=user.id,
    )

    uri = artifact.uri

    if uri.startswith(("https://", "http://", "s3://", "gs://", "az://")):
        raise HTTPException(
            status_code=400,
            detail="External URIs must be accessed via their respective protocols"
        )

    base_upload_dir = Path(settings.chat_upload_dir).resolve()
    file_path = (base_upload_dir / uri).resolve()

    if not file_path.is_relative_to(base_upload_dir):
        raise HTTPException(
            status_code=403,
            detail="Access denied: path traversal attempt"
        )

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if not file_path.is_file():
        raise HTTPException(status_code=400, detail="Not a file")

    try:
        file_bytes = file_path.read_bytes()[:1024]
        _, detected_mime = detect_mime_from_magic_bytes(file_bytes)
    except Exception:
        detected_mime = "application/octet-stream"

    content_disposition = get_content_disposition_header(detected_mime, str(artifact.id))

    return FileResponse(
        path=str(file_path),
        media_type=detected_mime,
        headers={
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
            "Content-Disposition": content_disposition,
            "Cache-Control": "private, max-age=3600",
        }
    )
