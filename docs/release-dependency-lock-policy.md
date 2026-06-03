# Release Dependency Lock Policy

Status: active release policy.

Last updated: 2026-06-03.

## Goal

Release builds must be reproducible. Development manifests may keep practical
version ranges, but a release candidate must record the exact dependency graph
used for verification.

## Frontend

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
- Do not run `npm install` for release verification unless intentionally
  updating `package-lock.json`.
- Any dependency update must include the changed `package.json` and
  `package-lock.json` together.

## Platform API

- Source manifests: `apps/platform-api-app/pyproject.toml` and
  `apps/platform-api-app/requirements.txt`.
- Current release risk: backend requirements are lower-bound ranges, not a
  full lock.
- Release candidate lock artifact: generate a constraints file from the
  verified environment, for example `apps/platform-api-app/requirements.lock`.
- Release install command once a lock exists:

```powershell
cd apps/platform-api-app
python -m pip install -r requirements.txt -c requirements.lock
python -m pytest -q
python -m alembic upgrade head
```

Rules:

- Do not broaden backend dependency ranges in a release candidate without
  running platform API tests and migration checks.
- If `requirements.lock` is absent, the release checklist must mark backend
  dependency locking as a known open release gate.
- `requirements.lock` should be regenerated only after dependency updates are
  intentionally reviewed.

## Root Agent Library

- Source manifest: `pyproject.toml`.
- Source requirements: `requirements.txt`.
- Release verification command:

```powershell
python -m pytest tests -q
```

Rules:

- Root library dependency changes must be tested independently from the
  platform API app.
- Agent/plugin tests that rely on external LLM providers must either use a
  deterministic skip reason or explicit provider credentials in the release
  evidence.

## Required Release Evidence

Every release candidate must record:

- Commit SHA.
- Frontend `npm ci` result or an explicit note that the lock was not changed.
- Frontend typecheck/lint/test/build results.
- Backend dependency lock or known-risk entry.
- Platform API pytest result.
- Migration upgrade result.
- Any intentionally accepted dependency risk.

## Rollback

Dependency rollback uses the previous release commit and its lock artifacts.
If a dependency update causes runtime failure, roll back both the manifest and
lock/constraints file together.
