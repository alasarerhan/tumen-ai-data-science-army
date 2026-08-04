from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any
from urllib import error, request

DEFAULT_API_URL = "http://127.0.0.1:8010"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Query the Universal Platform Control Plane API.")
    parser.add_argument("--api-url", default=os.getenv("PLATFORM_API_URL", DEFAULT_API_URL))
    parser.add_argument("--token", default=os.getenv("PLATFORM_API_TOKEN"))
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("catalog")

    query = sub.add_parser("query")
    query.add_argument("text")
    query.add_argument("--workspace-id", required=True)
    query.add_argument("--resource-key", action="append", dest="resource_keys")
    query.add_argument("--limit", type=int)

    plan = sub.add_parser("plan-action")
    plan.add_argument("--workspace-id", required=True)
    plan.add_argument("--query")
    plan.add_argument("--action-name")
    plan.add_argument("--arguments-json", default="{}")

    execute = sub.add_parser("execute-action")
    execute.add_argument("--workspace-id", required=True)
    execute.add_argument("--action-name", required=True)
    execute.add_argument("--arguments-json", default="{}")
    execute.add_argument("--confirmed", action="store_true")

    args = parser.parse_args(argv)
    try:
        payload = _dispatch(args)
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _dispatch(args: argparse.Namespace) -> Any:
    if args.command == "catalog":
        return _call(args.api_url, "/v1/control-plane/catalog", token=args.token)
    if args.command == "query":
        body: dict[str, Any] = {"workspace_id": args.workspace_id, "query": args.text}
        if args.resource_keys:
            body["resource_keys"] = args.resource_keys
        if args.limit is not None:
            body["limit"] = args.limit
        return _call(
            args.api_url, "/v1/control-plane/query", method="POST", body=body, token=args.token
        )
    if args.command == "plan-action":
        body = {
            "workspace_id": args.workspace_id,
            "query": args.query,
            "action_name": args.action_name,
            "arguments": _loads_object(args.arguments_json),
        }
        return _call(
            args.api_url,
            "/v1/control-plane/actions/plan",
            method="POST",
            body=body,
            token=args.token,
        )
    if args.command == "execute-action":
        body = {
            "workspace_id": args.workspace_id,
            "action_name": args.action_name,
            "arguments": _loads_object(args.arguments_json),
            "confirmed": bool(args.confirmed),
        }
        return _call(
            args.api_url,
            "/v1/control-plane/actions/execute",
            method="POST",
            body=body,
            token=args.token,
        )
    raise RuntimeError(f"Unsupported command: {args.command}")


def _call(
    api_url: str,
    path: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    token: str | None = None,
) -> Any:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = request.Request(
        api_url.rstrip("/") + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {message}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Control Plane API unavailable: {exc.reason}") from exc


def _loads_object(value: str) -> dict[str, Any]:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("--arguments-json must be a JSON object")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
