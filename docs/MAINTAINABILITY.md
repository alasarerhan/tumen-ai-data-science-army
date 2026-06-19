# Maintainability & Release-Safety Notes

> Consolidated notes on dead-code triage, release-profile fallback behavior, and dependency lock policy.
> Replaces `docs/dead-code-dynamic-surface-triage.md`, `docs/release-profile-fallback-review.md`, and `docs/release-dependency-lock-policy.md`.

Last updated: 2026-06-03 (all three sources).

## 1. Dead-Code Dynamic Surface Triage

### Purpose

Separate dynamic/runtime code from ordinary dead-code candidates. Do not delete items in the protected categories below based only on static unused-symbol output.

### Protected Dynamic Surfaces

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

### Cleanup Rules

- Keep route handlers unless the route is removed from `main.py`, OpenAPI, tests, frontend callers, and docs.
- Keep registry-exposed agents/tools unless removed from registry bootstrap, aliases, workflow resolver rules, tests, and docs.
- Keep serialization DTO fields unless API contract tests and frontend consumers prove they are unused.
- Treat generated/test fixture code separately from production code.
- Prefer deprecation plus tests over immediate deletion for public API surfaces.

### Candidate Review Checklist

Before deleting a file/function:

1. Search direct references with `rg`.
2. Search string references, aliases, registry names, route paths, and DTO keys.
3. Check tests for monkeypatch, importlib, or fixture-only usage.
4. Check docs and API contract files.
5. Add or update a regression test proving the removal does not break the route, registry, workflow, or artifact path.

### Current Decision

No runtime/dynamic code was deleted in this pass. Cleanup remains allowed only after candidate-specific proof using the checklist above.

## 2. Release Profile Fallback Review

### Reviewed Surfaces

| Surface | Current behavior | Release safety decision | Evidence |
|---|---|---|---|
| Run orchestration creation | Local run id fallback only when `DEPLOYMENT_PROFILE=local` and `ALLOW_LOCAL_RUN_FALLBACK=true` | Safe; release raises validation/upstream errors instead of hiding orchestration failure | `tests/test_run_orchestration_service.py` |
| `staged_m22` runtime mode | Allowed only in local or staging profile | Safe until lifecycle parity is proven | `tests/test_run_orchestration_service.py` |
| Run log stream | Prefect logs are preferred; mock stream was previously available after provider failure | Fixed; mock logs are now local-only and release returns `503` when provider logs are unavailable | `tests/test_logs_release_fallback.py` |
| Chat fallback reply path | ChatWorkspace dependency/runtime fallback still returns deterministic assistant content | Accepted for design-partner scope; should be revisited before GA if release profile must require live graph execution | Existing chat service tests |
| Discovery fallback search | Uses curated/registry fallback when vector search is unavailable | Accepted; discovery remains a UX/search fallback, not a production execution substitute | `tests/test_agent_discovery.py` |

### Code Change

- `platform_api/routes/logs.py` no longer returns mock logs in release profile.
- Local mock log stream remains available only when `DEPLOYMENT_PROFILE=local` and `ALLOW_LOCAL_RUN_FALLBACK=true`.

### Verification

```powershell
cd apps/platform-api-app
python -m pytest tests/test_run_orchestration_service.py tests/test_logs_release_fallback.py -q
```

Result: 12 passed.

### Residual Risk

- Chat fallback is still intentionally product-friendly. Before GA, decide whether release profile should fail closed for ChatWorkspace dependency failures or continue returning deterministic fallback guidance.

## 3. Release Dependency Lock Policy

### Goal

Release builds must be reproducible. Development manifests may keep practical version ranges, but a release candidate must record the exact dependency graph used for verification.

### Frontend

- Source manifest: `frontend/package.json`.
- Lock file: `frontend/package-lock.json`.
- Release install command: `npm ci`.
- Release verification commands:

```powershell
cd frontend
npm ci
npm run typecheck
npm run lint
npm run test
npm run build
```

Rules:

- Do not edit `node_modules/`.
- Do not run `npm install` for release verification unless intentionally updating `package-lock.json`.
- Any dependency update must include the changed `package.json` and `package-lock.json` together.

### Platform API

- Source manifests: `apps/platform-api-app/pyproject.toml` and `apps/platform-api-app/requirements.txt`.
- Current release risk: backend requirements are lower-bound ranges, not a full lock.
- Release candidate lock artifact: generate a constraints file from the verified environment, for example `apps/platform-api-app/requirements.lock`.
- Release install command once a lock exists:

```powershell
cd apps/platform-api-app
python -m pip install -r requirements.txt -c requirements.lock
python -m pytest -q
python -m alembic upgrade head
```

Rules:

- Do not broaden backend dependency ranges in a release candidate without running platform API tests and migration checks.
- If `requirements.lock` is absent, the release checklist must mark backend dependency locking as a known open release gate.
- `requirements.lock` should be regenerated only after dependency updates are intentionally reviewed.

### Root Agent Library

- Source manifest: `pyproject.toml`.
- Source requirements: `requirements.txt`.
- Release verification command:

```powershell
python -m pytest tests -q
```

Rules:

- Root library dependency changes must be tested independently from the platform API app.
- Agent/plugin tests that rely on external LLM providers must either use a deterministic skip reason or explicit provider credentials in the release evidence.

### Required Release Evidence

Every release candidate must record:

- Commit SHA.
- Frontend `npm ci` result or an explicit note that the lock was not changed.
- Frontend typecheck/lint/test/build results.
- Backend dependency lock or known-risk entry.
- Platform API pytest result.
- Migration upgrade result.
- Any intentionally accepted dependency risk.

### Rollback

Dependency rollback uses the previous release commit and its lock artifacts. If a dependency update causes runtime failure, roll back both the manifest and lock/constraints file together.

---

**Source consolidation note**

- `docs/dead-code-dynamic-surface-triage.md` → §1 (purposes, protected surfaces, cleanup rules, candidate checklist, current decision).
- `docs/release-profile-fallback-review.md` → §2 (reviewed surfaces, code change, verification, residual risk).
- `docs/release-dependency-lock-policy.md` → §3 (frontend, platform API, root agent library, required evidence, rollback).
