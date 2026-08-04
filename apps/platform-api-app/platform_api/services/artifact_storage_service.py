from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from platform_api.core.config import settings
from platform_api.core.service_errors import ValidationError


@dataclass(frozen=True)
class ArtifactStorageBackend:
    backend: str
    root: str

    def build_uri(self, key: str) -> str:
        clean_key = key.strip().lstrip("/\\")
        if not clean_key:
            raise ValidationError("Artifact storage key is required")
        if self.backend == "local":
            return str((Path(self.root) / clean_key).as_posix())
        if self.backend == "s3":
            return f"s3://{self.root}/{clean_key}"
        if self.backend == "gcs":
            return f"gs://{self.root}/{clean_key}"
        raise ValidationError("Unsupported artifact storage backend")


def get_artifact_storage_backend() -> ArtifactStorageBackend:
    backend = settings.artifact_storage_backend.lower().strip()
    if backend == "local":
        return ArtifactStorageBackend(backend=backend, root=settings.artifact_storage_local_dir)
    if backend == "s3":
        if not settings.artifact_storage_s3_bucket:
            raise ValidationError("ARTIFACT_STORAGE_S3_BUCKET is required for s3 artifact storage")
        return ArtifactStorageBackend(backend=backend, root=settings.artifact_storage_s3_bucket)
    if backend == "gcs":
        if not settings.artifact_storage_gcs_bucket:
            raise ValidationError(
                "ARTIFACT_STORAGE_GCS_BUCKET is required for gcs artifact storage"
            )
        return ArtifactStorageBackend(backend=backend, root=settings.artifact_storage_gcs_bucket)
    raise ValidationError("ARTIFACT_STORAGE_BACKEND must be one of: local, s3, gcs")
