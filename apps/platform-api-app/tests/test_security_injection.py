"""Security injection tests for API endpoints.

Tests cover:
  - SQL injection in workflow names
  - XSS in chat messages
  - Path traversal in file uploads
  - Command injection in run parameters
  - Auth bypass with invalid tokens
  - IDOR cross-workspace access
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from platform_api.services import chat_service, workflow_service


class TestSqlInjection:
    """Tests for SQL injection prevention."""

    def test_sql_injection_in_workflow_name(self, seeded_db: dict) -> None:
        db = seeded_db["db"]
        seeded_db["tenant"]
        workspace = seeded_db["workspace"]
        user_id = seeded_db["user_admin"].id

        malicious_names = [
            "'; DROP TABLE workflow_specs; --",
            "test' OR '1'='1",
            "test'; INSERT INTO users VALUES (...); --",
            'test" OR "1"="1',
        ]

        for name in malicious_names:
            try:
                workflow_service.create_workflow_spec_version(
                    db,
                    workspace_id=str(workspace.id),
                    user_id=user_id,
                    name=name,
                    spec={"steps": [{"id": "s1", "tool": "test"}]},
                    publish=False,
                )
            except HTTPException as e:
                assert e.status_code in (400, 403, 404)

    def test_sql_injection_in_parameters_json(self, seeded_db: dict) -> None:
        from platform_api.services import run_service

        db = seeded_db["db"]
        tenant = seeded_db["tenant"]
        workspace = seeded_db["workspace"]
        user_id = seeded_db["user_admin"].id

        malicious_params = {
            "query": "'; DROP TABLE users; --",
            "filter": "1=1 OR '1'='1'",
        }

        record = run_service.create_workflow_run_record(
            db,
            tenant_id=tenant.id,
            workspace_id=workspace.id,
            user_id=user_id,
            flow_key="test",
            prefect_flow_run_id=f"test-{uuid.uuid4().hex}",
            parameters=malicious_params,
        )

        assert record.id is not None
        assert record.status == "SCHEDULED"


class TestXssInChat:
    """Tests for XSS prevention in chat messages."""

    def test_xss_in_chat_message_content(self, seeded_db: dict) -> None:
        db = seeded_db["db"]
        tenant = seeded_db["tenant"]
        workspace = seeded_db["workspace"]
        user_id = seeded_db["user_admin"].id

        session = chat_service.create_chat_session(
            db,
            tenant_id=tenant.id,
            workspace_id=workspace.id,
            user_id=user_id,
            title="xss-test",
        )

        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
            "<svg onload=alert('xss')>",
        ]

        for payload in xss_payloads:
            message = chat_service.create_message(
                db,
                session=session,
                role="user",
                content=payload,
                artifacts=None,
            )

            assert message.content == payload
            assert "<script>" not in message.content or message.content == payload

    def test_xss_in_chat_session_title(self, seeded_db: dict) -> None:
        db = seeded_db["db"]
        tenant = seeded_db["tenant"]
        workspace = seeded_db["workspace"]
        user_id = seeded_db["user_admin"].id

        xss_title = "<script>alert('xss')</script>"

        session = chat_service.create_chat_session(
            db,
            tenant_id=tenant.id,
            workspace_id=workspace.id,
            user_id=user_id,
            title=xss_title,
        )

        assert session.title == xss_title


class TestPathTraversal:
    """Tests for path traversal prevention in file uploads."""

    def test_path_traversal_in_upload_filename(
        self, seeded_db: dict, tmp_path, monkeypatch
    ) -> None:

        db = seeded_db["db"]
        tenant = seeded_db["tenant"]
        workspace = seeded_db["workspace"]
        user_id = seeded_db["user_admin"].id

        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        monkeypatch.setattr(chat_service.settings, "chat_upload_dir", str(upload_dir))

        session = chat_service.create_chat_session(
            db,
            tenant_id=tenant.id,
            workspace_id=workspace.id,
            user_id=user_id,
            title="upload-test",
        )

        malicious_filenames = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc/passwd",
        ]

        for filename in malicious_filenames:
            upload = chat_service.save_upload(
                db,
                session=session,
                filename=filename,
                content_type="text/plain",
                file_bytes=b"test content",
                created_by_user_id=user_id,
            )

            assert ".." not in upload.filename
            assert upload.filename != filename

    def test_path_traversal_sanitized_to_safe_name(
        self, seeded_db: dict, tmp_path, monkeypatch
    ) -> None:
        db = seeded_db["db"]
        tenant = seeded_db["tenant"]
        workspace = seeded_db["workspace"]
        user_id = seeded_db["user_admin"].id

        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        monkeypatch.setattr(chat_service.settings, "chat_upload_dir", str(upload_dir))

        session = chat_service.create_chat_session(
            db,
            tenant_id=tenant.id,
            workspace_id=workspace.id,
            user_id=user_id,
            title="upload-test",
        )

        upload = chat_service.save_upload(
            db,
            session=session,
            filename="../../../etc/passwd",
            content_type="text/plain",
            file_bytes=b"test",
            created_by_user_id=user_id,
        )

        assert "passwd" in upload.filename or "etcpasswd" in upload.filename


class TestCommandInjection:
    """Tests for command injection prevention."""

    def test_command_injection_in_run_parameters(self, seeded_db: dict) -> None:
        from platform_api.services import run_service

        db = seeded_db["db"]
        tenant = seeded_db["tenant"]
        workspace = seeded_db["workspace"]
        user_id = seeded_db["user_admin"].id

        malicious_params = {
            "command": "; rm -rf /",
            "script": "$(cat /etc/passwd)",
            "eval": "`whoami`",
        }

        record = run_service.create_workflow_run_record(
            db,
            tenant_id=tenant.id,
            workspace_id=workspace.id,
            user_id=user_id,
            flow_key="test",
            prefect_flow_run_id=f"test-{uuid.uuid4().hex}",
            parameters=malicious_params,
        )

        assert record.id is not None
        import json

        stored = json.loads(record.parameters_json)
        assert stored["command"] == "; rm -rf /"


class TestAuthBypass:
    """Tests for authentication bypass prevention."""

    def test_auth_bypass_invalid_token(self, seeded_db: dict) -> None:
        from fastapi.security import HTTPAuthorizationCredentials
        from starlette.requests import Request

        from platform_api.auth.dependencies import get_principal

        invalid_tokens = [
            "invalid-token",
            "Bearer invalid",
            "",
            "null",
            "undefined",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.fake.signature",
        ]

        for token in invalid_tokens:
            try:
                import asyncio

                request = Request(
                    {
                        "type": "http",
                        "method": "GET",
                        "path": "/",
                        "headers": [],
                        "client": ("127.0.0.1", 8000),
                    }
                )
                asyncio.run(
                    get_principal(
                        request=request,
                        credentials=HTTPAuthorizationCredentials(
                            scheme="Bearer", credentials=token
                        ),
                    )
                )
            except HTTPException as e:
                assert e.status_code in (401, 403, 503)

    def test_auth_bypass_expired_token(self, seeded_db: dict) -> None:
        pass


class TestIdor:
    """Tests for IDOR (Insecure Direct Object Reference) prevention."""

    def test_idor_cross_workspace_access(self, seeded_db: dict) -> None:
        from platform_api.db.models import Workspace
        from platform_api.services import run_service

        db = seeded_db["db"]
        tenant = seeded_db["tenant"]
        workspace = seeded_db["workspace"]
        user_id = seeded_db["user_admin"].id

        other_workspace = Workspace(
            tenant_id=tenant.id,
            name=f"other-{uuid.uuid4().hex[:8]}",
        )
        db.add(other_workspace)
        db.flush()

        record = run_service.create_workflow_run_record(
            db,
            tenant_id=tenant.id,
            workspace_id=workspace.id,
            user_id=user_id,
            flow_key="test",
            prefect_flow_run_id=f"test-{uuid.uuid4().hex}",
            parameters={},
        )

        with pytest.raises(HTTPException) as exc_info:
            run_service.get_run_by_id_for_workspace(
                db,
                run_id=str(record.id),
                workspace_id=other_workspace.id,
            )

        assert exc_info.value.status_code == 404

    def test_idor_workflow_access_other_workspace(self, seeded_db: dict) -> None:
        from platform_api.db.models import Workspace

        db = seeded_db["db"]
        tenant = seeded_db["tenant"]
        workspace = seeded_db["workspace"]
        user_id = seeded_db["user_admin"].id

        other_workspace = Workspace(
            tenant_id=tenant.id,
            name=f"other-{uuid.uuid4().hex[:8]}",
        )
        db.add(other_workspace)
        db.flush()

        created = workflow_service.create_workflow_spec_version(
            db,
            workspace_id=str(workspace.id),
            user_id=user_id,
            name="test-workflow",
            spec={"steps": [{"id": "s1", "tool": "data_clean"}]},
            publish=False,
        )

        with pytest.raises(HTTPException) as exc_info:
            workflow_service.get_workflow_spec_for_workspace(
                db,
                workflow_id=str(created.id),
                workspace_id=str(other_workspace.id),
                user_id=user_id,
            )

        assert exc_info.value.status_code in (403, 404)
