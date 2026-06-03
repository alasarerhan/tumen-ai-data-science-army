from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    api_host: str = "127.0.0.1"
    api_port: int = 8000

    deployment_profile: str = "release"  # local|staging|release

    auth_mode: str = "oidc"  # dev|oidc
    dev_auth_token: str = ""
    dev_auth_email: str = "dev@example.local"
    oidc_issuer: str = "https://accounts.google.com"
    oidc_audience: str = ""
    oidc_jwks_url: str = ""
    oidc_require_verified_email: bool = True
    oidc_allowed_email_domains: str = ""
    allow_self_service_tenant_creation: bool = False
    return_invite_tokens_in_local: bool = False
    csrf_enabled: bool = True
    csrf_exempt_paths: str = "/health,/healthz,/metrics,/v1/auth/csrf,/v1/auth/login/dev"

    database_url: str = "sqlite:///./platform.db"
    tenant_write_quota_per_minute: int = 120

    # CORS
    cors_origins: str = (
        "http://localhost:3000,"
        "http://localhost:4173,"
        "http://localhost:5173,"
        "http://localhost:5174,"
        "http://127.0.0.1:5173,"
        "http://127.0.0.1:5174"
    )

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_model_strategy: str = "gpt-3.5-turbo"
    openai_cache_ttl_seconds: int = 3600
    openai_cache_enabled: bool = True

    # Chat workspace
    chat_upload_dir: str = "./.chat_uploads"
    chat_stream_chunk_ms: int = 35
    chat_worker_max_threads: int = 4
    chat_upload_max_mb: int = 50
    data_source_secret_key: str = ""

    # Signal stream
    signal_stream_poll_ms: int = 500
    signal_stream_max_idle_polls: int = 10
    signal_stream_close_idle_polls: int = 2

    # Orchestration
    allow_local_run_fallback: bool = False
    orchestration_execution_mode: str = "prefect"  # prefect|staged_m22
    orchestration_state_redis_url: str = ""
    workflow_queue_redis_url: str = ""
    workflow_queue_required: bool = False
    prefect_hello_deployment_id: str = ""
    prefect_default_deployment_id: str = ""
    prefect_work_pool_name: str = ""
    prefect_work_queue_name: str = ""

    # Agent caching (FinOps)
    agent_cache_enabled: bool = True
    agent_cache_ttl_seconds: int = 3600
    agent_cache_redis_url: str = ""

    # Storage retention (FinOps)
    artifact_retention_days: int = 90
    artifact_storage_backend: str = "local"  # local|s3|gcs
    artifact_storage_local_dir: str = "./.artifacts"
    artifact_storage_s3_bucket: str = ""
    artifact_storage_gcs_bucket: str = ""
    audit_log_retention_days: int = 90
    log_retention_days: int = 30

    # Webhook retry (FinOps)
    webhook_max_retries: int = 5
    webhook_backoff_base_seconds: float = 1.0
    webhook_backoff_max_seconds: float = 300.0
    egress_allowed_hosts: str = "accounts.google.com,localhost,127.0.0.1"
    egress_strict_mode: bool = True
    artifact_redirect_allowed_hosts: str = ""
    artifact_redirect_strict_mode: bool = True
    malware_scan_mode: str = "scan-tag"  # off|scan-tag|block-on-detect

    # Scheduler settings
    artifact_cleanup_interval_seconds: int = 3600
    outbox_process_interval_seconds: int = 5
    dlq_alert_threshold: int = 10
    scheduler_leader_ttl_seconds: int = 60
    scheduler_poll_interval_seconds: float = 5.0
    scheduler_job_timeout_seconds: int = 300
    scheduler_max_concurrent_jobs: int = 2

    # External service timeouts
    prefect_api_timeout_seconds: int = 30
    oidc_jwks_timeout_seconds: int = 10
    database_query_timeout_seconds: int = 60

    # Graceful shutdown
    shutdown_timeout_seconds: int = 30

    def is_local_profile(self) -> bool:
        return self.deployment_profile.lower() == "local"

    def is_staging_profile(self) -> bool:
        return self.deployment_profile.lower() == "staging"

    def is_local_or_staging_profile(self) -> bool:
        return self.is_local_profile() or self.is_staging_profile()

    def is_production_profile(self) -> bool:
        return self.deployment_profile.lower() in {"prod", "production"}

    def validate_directories(self) -> None:
        """Validate that required directories exist and are writable.

        Raises
        ------
        RuntimeError
            If any required directory is not writable.
        """
        upload_dir = Path(self.chat_upload_dir).resolve()
        try:
            upload_dir.mkdir(parents=True, exist_ok=True)
            if not os.access(upload_dir, os.W_OK):
                raise RuntimeError(
                    f"Upload directory {upload_dir} is not writable. "
                    f"Set CHAT_UPLOAD_DIR environment variable to a writable directory."
                )
        except PermissionError as e:
            raise RuntimeError(
                f"Cannot create upload directory {upload_dir}: {e}. "
                f"Set CHAT_UPLOAD_DIR environment variable to a writable directory."
            ) from e

        backend = self.artifact_storage_backend.lower().strip()
        if backend not in {"local", "s3", "gcs"}:
            raise RuntimeError("ARTIFACT_STORAGE_BACKEND must be one of: local, s3, gcs")
        if self.is_production_profile() and backend == "local":
            raise RuntimeError("Production deployments must use object storage for artifacts")


settings = Settings()
