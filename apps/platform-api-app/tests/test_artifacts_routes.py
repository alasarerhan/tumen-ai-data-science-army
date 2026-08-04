from __future__ import annotations

from fastapi.testclient import TestClient

from platform_api.auth.dependencies import get_principal
from platform_api.auth.models import Principal
from platform_api.db.session import get_db
from platform_api.main import create_app
from platform_api.services.artifact_service import create_artifact_record


def test_list_artifacts_returns_safe_lineage_fields_and_honors_kind_filter(
    seeded_db: dict[str, object],
) -> None:
    app = create_app()
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    user = seeded_db["user_admin"]

    parent = create_artifact_record(
        db,
        workspace_id=str(workspace.id),
        workflow_run_id=None,
        kind="dataset",
        uri="local://artifacts/input.csv",
        user_id=user.id,
        produced_by_node_id="ingest",
    )
    child = create_artifact_record(
        db,
        workspace_id=str(workspace.id),
        workflow_run_id=None,
        kind="model",
        uri="local://artifacts/model.pkl",
        user_id=user.id,
        produced_by_node_id="train",
        parent_artifact_ids=[str(parent.id)],
    )
    _off_kind = create_artifact_record(
        db,
        workspace_id=str(workspace.id),
        workflow_run_id=None,
        kind="metrics",
        uri="local://artifacts/metrics.json",
        user_id=user.id,
        parent_artifact_ids=[str(child.id)],
    )
    db.commit()

    principal = Principal(sub=user.sub, email=user.email, claims={})

    def _principal() -> Principal:
        return principal

    def _db():
        yield db

    app.dependency_overrides[get_principal] = _principal
    app.dependency_overrides[get_db] = _db
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(f"/v1/artifacts?workspace_id={workspace.id}&kind=model")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["id"] == str(child.id)
    assert item["workspace_id"] == str(workspace.id)
    assert item["tenant_id"] == str(tenant.id)
    assert item["produced_by_node_id"] == "train"
    assert item["parent_artifact_ids"] == [str(parent.id)]
    assert item["artifact_type"] == "model"
    assert item["storage_uri"] == "local://artifacts/model.pkl"
