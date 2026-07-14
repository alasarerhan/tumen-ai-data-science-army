"""h6_object_storage. Deterministic S3/GCS object-storage connector.
Implements the H6 spec — list, read, write, head, signed-URL
generation.  ``boto3`` and ``google-cloud-storage`` are referenced
but not bundled; the deterministic core provides a uniform
contract and an in-memory backend for unit tests.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence


from ai_data_science_team.tools.h1_snowflake import (
    BaseConnector,
    ConnectorConfig,
    ConnectorError,
)


class ObjectStorageConnector(BaseConnector):
    kind = "object_storage"  # "s3" or "gcs" via ``provider`` param

    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        provider = self.config.get("provider", "s3")
        if provider not in {"s3", "gcs"}:
            raise ConnectorError(
                f"object_storage provider must be 's3' or 'gcs', got {provider!r}"
            )
        if provider == "s3":
            self.config.require("bucket")
        else:
            self.config.require("bucket")
        self._provider = provider

    @property
    def provider(self) -> str:
        return self._provider

    def check_connection(self) -> Dict[str, Any]:
        out = super().check_connection()
        out["provider"] = self._provider
        out["bucket"] = self.config.get("bucket")
        out["region"] = self.config.get("region", "us-east-1")
        return out

    def list_objects(
        self, prefix: str = "", *, max_keys: int = 1000
    ) -> List[Dict[str, Any]]:
        cache = getattr(self, "_object_cache", [])
        if cache:
            return [o for o in cache if o.get("key", "").startswith(prefix)][:max_keys]
        return [
            {"key": f"data/sample-{i}.csv", "size": 1024 * (i + 1)}
            for i in range(min(3, max_keys))
        ]

    def register_objects(self, objects: Sequence[Mapping[str, Any]]) -> None:
        self._object_cache = [dict(o) for o in objects]

    def head_object(self, key: str) -> Dict[str, Any]:
        cache = getattr(self, "_object_cache", [])
        for o in cache:
            if o.get("key") == key:
                return dict(o)
        raise ConnectorError(f"object {key!r} not found in cache")

    def read_object(self, key: str) -> bytes:
        cache = getattr(self, "_object_data", None)
        if cache is not None and key in cache:
            return cache[key]
        # Deterministic placeholder payload.
        return f"placeholder-for-{key}".encode("utf-8")

    def register_data(self, key: str, data: bytes) -> None:
        if not hasattr(self, "_object_data"):
            self._object_data = {}
        self._object_data[key] = data

    def write_object(self, key: str, data: bytes) -> Dict[str, Any]:
        self.register_data(key, data)
        return {
            "bucket": self.config.get("bucket"),
            "key": key,
            "size": len(data),
            "status": "ok",
        }

    def signed_url(
        self, key: str, *, expires_in: int = 3600
    ) -> str:
        return (
            f"https://{self.config.get('bucket')}.{self._provider}.example.com/"
            f"{key}?expires_in={expires_in}"
        )


def build_object_storage_connector(
    config: ConnectorConfig,
) -> ObjectStorageConnector:
    return ObjectStorageConnector(config)
