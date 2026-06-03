# Task Status Review - 2026-06-03

## Scope

Reviewed the active backlog in `tasks.md` against the current working tree and reran the release-relevant gates that can run locally without a long-lived app stack.

## Current Git State

The repo is attached to `origin/main`, but the working tree remains intentionally dirty while this review applies fixes and records evidence. Runtime/generated folders such as `frontend/playwright-report/`, `frontend/test-results/`, `graphify-out/`, `outputs/`, and local DB/log files still need push hygiene before staging.

## Evidence Captured

| Gate | Result | Notes |
|------|--------|-------|
| Frontend typecheck | Passed | `npm.cmd run typecheck` |
| Frontend lint | Passed with warnings | `npm.cmd run lint`; 0 errors, 15 warnings remain |
| Frontend unit tests | Passed | `npm.cmd run test`; 35 files / 226 tests passed |
| Frontend build | Passed with chunk warning | `npm.cmd run build`; bundle warning only |
| Platform API tests | Passed | `python -m pytest -q`; 684 passed, 11 skipped |
| Root Python tests | Passed | `python -m pytest tests -q`; 94 passed |
| Selected agent/plugin tests | Passed | 353 passed with `--basetemp .tmp-tests/plugin-basetemp` |
| Migration check | Passed | SQLite temp DB `alembic upgrade head` through `0017_workflow_ir_v2` |
| Playwright golden path | Open | Port/config and login fixture blockers fixed. Login spec now reaches the app: 3/4 passed in full-file run; isolated `already authenticated` passed. Full suite remains open because repeated local auth attempts can trigger `/v1/auth/login/dev` rate limiting. |

## Fixes Applied During Review

- Fixed ESLint typed-rule configuration, ignored Playwright generated output folders, and updated login e2e helpers for the current collapsed developer-token UI.
- Fixed promise catch callback typing and an empty catch block.
- Made OIDC missing JWKS return `503` instead of `500`.
- Updated stale workflow tests to use a known agent alias instead of `tool: test`.
- Made real LLM workflow executor test skip cleanly on OpenAI quota exhaustion.
- Preserved consumed workflow signals in `SignalStore.list_all()` until explicit cleanup.
- Restored numeric CloudOps monthly cost artifact while retaining decimal string detail.
- Made dynamic workflow resolution produce a deterministic fallback spec when the LLM is unavailable or returns invalid output.
- Fixed `SQLConnector` SQLite engine creation by not passing TCP pool timeout arguments to SQLite.

## Still Open

- Playwright e2e is not closed; webServer readiness and login selector issues are fixed, but the full suite still needs a clean run strategy that avoids local auth rate-limit noise.
- Live backend/frontend smoke is partially closed: `/healthz`, frontend load, dev login, and browser-context `/v1/me` passed; workflow/run flow is still pending.
- Release metadata, owner names, monitoring links, and rollback sign-off fields are still placeholders.
- Full tenant/workspace route matrix is still not documented even though targeted tenant/admin tests pass.
- Security findings still need explicit triage status per item in `security-report/verified-findings.md`.
