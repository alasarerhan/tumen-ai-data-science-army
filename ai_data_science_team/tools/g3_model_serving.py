"""
g3_model_serving
================

Deterministic tools supporting **G3 — Gerçek Model Serving / Deploy**
(spec ``docs/specs/G3-model-serving.md``).

Implements the deterministic scaffold-rollout layer: Dockerfile /
bentofile / FastAPI template rendering, deployment record CRUD,
port allocation, rollback decision logic. The actual subprocess /
docker-side execution sits in the workflow layer (out of scope here).

Public surface
--------------

* :func:`allocate_port` — pick a free local port from the deployment
  pool (8100-8199 by default).
* :func:`render_dockerfile` — produce a Dockerfile for the model
  artifacts dict.
* :func:`render_bentofile` — produce a bentofile.yaml for the same.
* :func:`render_fastapi_app` — produce a FastAPI scaffold.
* :func:`record_deployment` — build a deployment record.
* :func:`record_rollback` — build a rollback record.
* :func:`G3_SERVING_TOOL_NAMES` — registry constant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Port allocation
# ---------------------------------------------------------------------------


PORT_POOL: range = range(8100, 8199)


def allocate_port(used_ports: Optional[Iterable[int]] = None) -> int:
    """Return the first free port in PORT_POOL."""
    used = set(used_ports or [])
    for p in PORT_POOL:
        if p not in used:
            return int(p)
    # Pool exhausted; round-robin / fail fast by reusing the head.
    if PORT_POOL:
        return int(PORT_POOL[0])
    raise RuntimeError("empty port pool")


# ---------------------------------------------------------------------------
# Templates (Jinja2-style placeholders, rendered as literal strings so
# the tool is LLM-free and inspectable).
# ---------------------------------------------------------------------------


def render_dockerfile(
    model_id: str,
    version: str,
    *,
    python_version: str = "3.11",
    base_image: str = "python:",
) -> str:
    """Return a Dockerfile body for serving ``model_id`` v``version``."""
    return (
        f"FROM {base_image}{python_version}-slim\n"
        f"ENV MODEL_ID={model_id} MODEL_VERSION={version}\n"
        "WORKDIR /app\n"
        "COPY requirements.txt .\n"
        "RUN pip install --no-cache-dir -r requirements.txt\n"
        "COPY app ./app\n"
        "EXPOSE 8000\n"
        'CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]\n'
    )


def render_bentofile(
    model_id: str,
    version: str,
    *,
    service: str = "scoring_service.py",
) -> str:
    """Return a bentofile.yaml body for serving ``model_id`` v``version``."""
    return (
        "service: \"scoring_service:svc\"\n"
        "labels:\n"
        "  owner: ai-data-science-team\n"
        f"  model_id: \"{model_id}\"\n"
        f"  model_version: \"{version}\"\n"
        "include:\n"
        "  - \"app.py\"\n"
        f"python:\n"
        "  packages:\n"
        "    - scikit-learn\n"
        '    - pandas\n  requirements_txt: "requirements.txt"\n'
        f"  start_cmds:\n"
        '    - "bentoml serve {service} --port 3000"\n'
    )


def render_fastapi_app(
    model_id: str,
    version: str,
    *,
    route: str = "/predict",
) -> str:
    """Return a FastAPI ``app/main.py`` body."""
    return (
        '"""\n'
        f"Generated model-serving scaffold for {model_id} v{version}.\n"
        '"""\n'
        "from fastapi import FastAPI, HTTPException\n"
        "from pydantic import BaseModel\n"
        "\n"
        "app = FastAPI(title=f\"{model_id}::{version}\")\n"
        "\n"
        "class PredictRequest(BaseModel):\n"
        "    features: dict\n"
        "\n"
        "@app.get('/healthz')\n"
        "def healthz() -> dict:\n"
        "    return {'status': 'ok'}\n"
        "\n"
        f"@app.post('{route}')\n"
        "def predict(req: PredictRequest):\n"
        "    if not isinstance(req.features, dict):\n"
        "        raise HTTPException(status_code=400, detail='features must be a dict')\n"
        "    # Real implementations would call ``model.predict(req.features)``;\n"
        "    # this scaffold provides a stable contract surface.\n"
        "    return {'prediction': None, 'model_id': '" + model_id + "', 'version': '" + version + "'}\n"
    )


# ---------------------------------------------------------------------------
# Deployment records
# ---------------------------------------------------------------------------


@dataclass
class DeploymentRecord:
    deployment_id: str
    model_id: str
    version: str
    target: str  # "endpoint" | "batch" | "container"
    status: str  # "pending" | "running" | "failed" | "rolled_back"
    port: Optional[int] = None
    created_at: Optional[str] = None
    artifacts: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "deployment_id": self.deployment_id,
            "model_id": self.model_id,
            "version": self.version,
            "target": self.target,
            "status": self.status,
            "port": self.port,
            "created_at": self.created_at,
            "artifacts": dict(self.artifacts),
        }


def record_deployment(
    model_id: str,
    version: str,
    target: str,
    *,
    deployment_id: Optional[str] = None,
    status: str = "pending",
    port: Optional[int] = None,
    created_at: Optional[str] = None,
    artifacts: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a deployment record (used by the workflow runtime)."""
    import uuid as _uuid

    return DeploymentRecord(
        deployment_id=deployment_id or _uuid.uuid4().hex,
        model_id=model_id,
        version=version,
        target=target,
        status=status,
        port=port,
        created_at=created_at,
        artifacts=dict(artifacts or {}),
    ).to_dict()


@dataclass
class RollbackRecord:
    deployment_id: str
    from_version: str
    to_version: str
    reason: Optional[str] = None
    decided_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "deployment_id": self.deployment_id,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "reason": self.reason,
            "decided_at": self.decided_at,
        }


def record_rollback(
    deployment_id: str,
    from_version: str,
    to_version: str,
    *,
    reason: Optional[str] = None,
    decided_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a rollback record."""
    return RollbackRecord(
        deployment_id=deployment_id,
        from_version=from_version,
        to_version=to_version,
        reason=reason,
        decided_at=decided_at,
    ).to_dict()


__all__ = [
    "PORT_POOL",
    "allocate_port",
    "render_dockerfile",
    "render_bentofile",
    "render_fastapi_app",
    "record_deployment",
    "record_rollback",
    "G3_SERVING_TOOL_NAMES",
]


G3_SERVING_TOOL_NAMES = [
    "g3_allocate_port",
    "g3_render_dockerfile",
    "g3_render_bentofile",
    "g3_render_fastapi_app",
    "g3_record_deployment",
    "g3_record_rollback",
]
