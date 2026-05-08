from __future__ import annotations

import json
import urllib.error
import urllib.request


BASE_URL = "http://localhost:8000"


def request(path: str, method: str = "GET", body: dict | None = None, token: str | None = None) -> dict:
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        payload = resp.read().decode("utf-8")
        return json.loads(payload) if payload else {}


def main() -> int:
    try:
        health = request("/healthz")
        print("healthz:", health)

        me = request("/v1/me", token="dev")
        print("me:", {"sub": me.get("sub"), "email": me.get("email")})

        tenant = request(
            "/v1/provisioning/tenants",
            method="POST",
            body={"name": "smoke-tenant"},
            token="dev",
        )
        tenant_id = tenant["tenant_id"]
        print("tenant:", tenant)

        workspace = request(
            "/v1/provisioning/workspaces",
            method="POST",
            body={"tenant_id": tenant_id, "name": "smoke-workspace"},
            token="dev",
        )
        workspace_id = workspace["workspace_id"]
        print("workspace:", workspace)

        invite = request(
            "/v1/provisioning/invites",
            method="POST",
            body={
                "tenant_id": tenant_id,
                "workspace_id": workspace_id,
                "email": "dev@example.com",
                "role": "member",
                "expires_in_hours": 48,
            },
            token="dev",
        )
        print("invite-created:", {"invite_id": invite.get("invite_id")})

        accepted = request(
            "/v1/provisioning/invites/accept",
            method="POST",
            body={"token": invite["token"]},
            token="dev",
        )
        print("invite-accepted:", accepted)

        runs = request(f"/v1/runs?workspace_id={workspace_id}", token="dev")
        print("runs-count:", len(runs.get("items", [])))

        artifact = request(
            "/v1/artifacts",
            method="POST",
            body={
                "workspace_id": workspace_id,
                "kind": "report",
                "uri": f"gs://dummy/{tenant_id}/{workspace_id}/report.json",
            },
            token="dev",
        )
        artifact_id = artifact["id"]
        print("artifact-created:", {"id": artifact_id})

        artifact_list = request(f"/v1/artifacts?workspace_id={workspace_id}", token="dev")
        print("artifact-count:", len(artifact_list.get("items", [])))

        access = request(
            f"/v1/artifacts/{artifact_id}/access?workspace_id={workspace_id}",
            token="dev",
        )
        print("artifact-access:", access.get("access_mode"))

        workflow = request(
            "/v1/workflows",
            method="POST",
            body={
                "workspace_id": workspace_id,
                "name": "smoke-workflow",
                "spec": {
                    "steps": [
                        {"id": "load", "tool": "data_loader"},
                        {"id": "eda", "tool": "eda_tools"},
                    ]
                },
                "publish": False,
            },
            token="dev",
        )
        workflow_id = workflow["id"]
        print("workflow-created:", {"name": workflow.get("name"), "version": workflow.get("version")})

        workflows = request(
            f"/v1/workflows?workspace_id={workspace_id}&name=smoke-workflow",
            token="dev",
        )
        print("workflow-count:", len(workflows.get("items", [])))

        latest = request(
            f"/v1/workflows/latest?workspace_id={workspace_id}&name=smoke-workflow",
            token="dev",
        )
        print("workflow-latest-version:", (latest.get("item") or {}).get("version"))

        by_id = request(
            f"/v1/workflows/{workflow_id}?workspace_id={workspace_id}",
            token="dev",
        )
        print("workflow-by-id:", {"id": by_id.get("id"), "status": by_id.get("status")})

        published = request(
            f"/v1/workflows/{workflow_id}/publish?workspace_id={workspace_id}",
            method="POST",
            token="dev",
        )
        print("workflow-published:", {"id": published.get("id"), "status": published.get("status")})

        strategy_report = request(
            f"/v1/strategy/reports/generate?workspace_id={workspace_id}",
            token="dev",
        )
        print("strategy-report:", strategy_report.get("summary", {}).get("run_count"))

        print("smoke test passed")
        return 0
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        print(f"http error: {exc.code} {exc.reason} body={body}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"smoke test failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
