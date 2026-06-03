# Dead-Code Dynamic Surface Triage

Status: conservative triage for cleanup planning.

Last updated: 2026-06-03.

## Purpose

This file separates dynamic/runtime code from ordinary dead-code candidates.
Do not delete items in the protected categories below based only on static
unused-symbol output.

## Protected Dynamic Surfaces

| Surface | Files | Why it is not a simple dead-code candidate |
|---|---|---|
| FastAPI route registration | `apps/platform-api-app/platform_api/main.py`, `apps/platform-api-app/platform_api/routes/*` | Routes are imported and registered through `app.include_router(...)`; individual handlers may only be referenced by HTTP paths and OpenAPI. |
| Frontend route tree | `frontend/src/main.tsx`, frontend route/screen modules | Screens may be reached through React Router and lazy render paths rather than direct imports in tests. |
| Agent registry | `ai_data_science_team/agent_registry.py`, `apps/platform-api-app/platform_api/orchestration/agent_catalog.py` | Agents are registered by metadata and module strings; registry lookups happen at runtime. |
| Tool registry | `ai_data_science_team/tool_registry.py`, `ai_data_science_team/tools/*` | Tools are discovered and invoked through registry metadata and dynamic agent plans. |
| Connector entry points | `ai_data_science_team/connectors/__init__.py` | Connectors can be discovered through Python entry points. |
| Workflow resolver/runtime engine | `ai_data_science_team/workflow_resolver.py`, `ai_data_science_team/runtime_engine.py` | Dynamic, supervised, and manual scenarios select agents and steps from runtime payloads. |
| Chat workspace fallback/agent path | `ai_data_science_team/multiagents/chat_workspace.py`, `apps/platform-api-app/platform_api/services/chat_service.py` | Chat execution can route through optional graph dependencies or fallback paths. |
| HITL/signals/runtime state | `ai_data_science_team/signals.py`, `apps/platform-api-app/platform_api/services/signal_service.py` | Signal keys and event payloads are serialized across SSE/runtime stores. |
| Artifact/report/chart rendering | `frontend/src/app/components/chat/*`, `frontend/src/app/components/charts/*` | Payload shape is backend-generated and may not appear as direct static calls. |

## Cleanup Rules

- Keep route handlers unless the route is removed from `main.py`, OpenAPI, tests,
  frontend callers, and docs.
- Keep registry-exposed agents/tools unless removed from registry bootstrap,
  aliases, workflow resolver rules, tests, and docs.
- Keep serialization DTO fields unless API contract tests and frontend consumers
  prove they are unused.
- Treat generated/test fixture code separately from production code.
- Prefer deprecation plus tests over immediate deletion for public API surfaces.

## Candidate Review Checklist

Before deleting a file/function:

1. Search direct references with `rg`.
2. Search string references, aliases, registry names, route paths, and DTO keys.
3. Check tests for monkeypatch, importlib, or fixture-only usage.
4. Check docs and API contract files.
5. Add or update a regression test proving the removal does not break the route,
   registry, workflow, or artifact path.

## Current Decision

No runtime/dynamic code was deleted in this pass. Cleanup remains allowed only
after candidate-specific proof using the checklist above.
