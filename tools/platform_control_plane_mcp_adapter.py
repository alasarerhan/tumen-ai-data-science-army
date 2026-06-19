from __future__ import annotations

import json
import os
import sys
from typing import Any

from platform_control_plane_cli import _call


API_URL = os.getenv("PLATFORM_API_URL", "http://127.0.0.1:8010")
TOKEN = os.getenv("PLATFORM_API_TOKEN")


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request_payload = json.loads(line)
            response = handle(request_payload)
        except Exception as exc:
            response = {"ok": False, "error": str(exc)}
        print(json.dumps(response, sort_keys=True), flush=True)
    return 0


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    method = payload.get("method")
    params = payload.get("params") or {}
    if method == "catalog":
        result = _call(API_URL, "/v1/control-plane/catalog", token=TOKEN)
    elif method == "query":
        result = _call(API_URL, "/v1/control-plane/query", method="POST", body=params, token=TOKEN)
    elif method == "actions.plan":
        result = _call(API_URL, "/v1/control-plane/actions/plan", method="POST", body=params, token=TOKEN)
    elif method == "actions.execute":
        result = _call(API_URL, "/v1/control-plane/actions/execute", method="POST", body=params, token=TOKEN)
    else:
        raise ValueError("Unsupported method")
    return {"ok": True, "result": result}


if __name__ == "__main__":
    raise SystemExit(main())
