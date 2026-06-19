# Verified Findings

## Verification Summary
- Raw potential findings reviewed: 11
- Verified findings: 5
- Fixed findings with regression evidence: 3
- Locally remediated findings requiring external owner attestation: 1
- Accepted-risk findings: 1
- Open verified findings: 1
- Eliminated as false positives/contextual non-issues: 6

## Eliminated Findings (False Positives)
- Dev login endpoint considered authentication bypass: rejected because guarded by both `AUTH_MODE=dev` and `DEPLOYMENT_PROFILE=local` checks.
- CORS wildcard concern: rejected; origins are explicit allowlist from config.
- Open redirect concern on artifact delivery: mitigated by host allowlist policy and strict mode.
- SQL injection concern in platform API routes: rejected for reviewed paths; SQLAlchemy parameterization patterns used.
- Path traversal concern in artifact streaming: rejected due resolved-path `is_relative_to` guard.
- OIDC token verification weakness: rejected; issuer/audience/algorithm verification is present.

## Verified Findings

### VF-001
- Source: `sc-rce`
- Severity: Critical
- Confidence: 95
- Title: Unsandboxed dynamic exec path with capability escape
- Decision: fix
- Owner: Platform security
- Target date: 2026-06-10
- Status: Fixed; regression covered, full security scan rerun pending
- Required evidence: SQL-agent direct query execution regression completed; full security scan rerun pending
- Files:
- `ai_data_science_team/templates/agent_templates.py:919`
- `ai_data_science_team/agents/sql_database_agent.py:827`
- Notes: Verified with local proof-of-behavior against helper execution path.
- Evidence:
- 2026-06-04 `node_func_execute_agent_from_sql_connection` no longer executes generated Python; it validates `sql_query_code` or AST-extracts a static legacy `sql_query` string, then calls `pd.read_sql` directly.
- 2026-06-04 `python -m pytest tests/test_sql_agent_security.py -q` passed 3 tests.
- 2026-06-04 `python -m pytest tests -q` passed 99 tests.

### VF-002
- Source: `sc-secrets`
- Severity: High
- Confidence: 98
- Title: Real OpenAI key in local .env files
- Decision: fix
- Owner: Platform operations
- Target date: 2026-06-09
- Status: Fixed; owner rotation attestation recorded and repo hygiene verified
- Required evidence: external key revoked/rotated by owner, tracked secret scan clean, and only ignored root `.env` contains the replacement runtime key
- Files:
- `.env:19`
- `apps/platform-api-app/.env:19`
- Evidence:
- 2026-06-04 `git ls-files -- .env apps/platform-api-app/.env frontend/.env` returned no tracked env files.
- 2026-06-04 root `.env` was recreated as the single local environment file with empty `OPENAI_API_KEY=`; `frontend/.env`, `frontend/.env.local`, and `apps/platform-api-app/.env` were removed.
- 2026-06-04 Vite `envDir` and backend `Settings` were updated so normal local development reads repo-root `.env`.
- 2026-06-04 `tools/secret_hygiene_scan.py` added to scan tracked files for OpenAI-style secret values without printing secret contents.
- 2026-06-09 credential owner added the rotated OpenAI project key to ignored repo-root `.env`; masked validation confirmed key present, normalized `sk-proj-*` shape, `.env` untracked, and no `frontend/.env`, `frontend/.env.local`, or `apps/platform-api-app/.env`.
- 2026-06-09 `python tools/secret_hygiene_scan.py` returned `No tracked OpenAI-style secret values found.`
- 2026-06-09 provider liveness check against `/v1/models` was attempted without printing the secret; this environment returned `URLError`, so provider availability is not claimed as verified from local runtime.

### VF-003
- Source: `sc-ci-cd`
- Severity: Medium
- Confidence: 90
- Title: Unpinned GitHub Actions tags
- Decision: accept
- Owner: DevOps
- Target date: 2026-06-14 for GA hardening review
- Status: Accepted for design-partner/local release scope; SHA pinning remains a GA hardening item
- Required evidence: accepted-risk record and workflow safety bugfix
- Files:
- `.github/workflows/ci.yml:53`
- `.github/workflows/release-gates.yml:21`
- `.github/workflows/rollout.yml:49`
- Evidence:
- 2026-06-04 accepted risk recorded because current release scope is local/design-partner validation, not production GA.
- 2026-06-04 no production deployment secrets are required by the local release checklist; Slack webhook usage remains guarded by GitHub secret presence.
- 2026-06-04 rollout workflow `monitor` job dependency fixed to include `validate-stage`, and Slack webhook shell arguments are quoted.
- Follow-up: pin third-party GitHub Actions to reviewed commit SHAs before GA or replace this accepted risk with a fixed decision.

### VF-004
- Source: `sc-iac`
- Severity: Medium
- Confidence: 88
- Title: Weak default DB secrets in IaC/dev deployment templates
- Decision: fix
- Owner: Platform operations
- Target date: 2026-06-10
- Status: Fixed; regression covered, full security scan rerun pending
- Required evidence: non-default secret requirement and deployment template regression completed; full security scan rerun pending
- Files:
- `apps/platform-api-app/helm/platform/templates/secret-db.yaml:25`
- `apps/platform-api-app/helm/platform/values.yaml:165`
- `apps/platform-api-app/docker-compose.yml:5`
- Evidence:
- 2026-06-04 Helm `secret-db.yaml` and bundled `postgres.yaml` reject missing/weak database passwords and no longer default to `changeme` or `postgres`.
- 2026-06-04 `docker-compose.yml` requires operator-provided `POSTGRES_PASSWORD` instead of `postgres:postgres`.
- 2026-06-04 `python -m pytest tests/test_iac_secret_defaults.py tests/test_m15_helm.py tests/test_m15_helm_rendering.py -q` passed 127 tests.
- 2026-06-04 `rtk pytest -q` in `apps/platform-api-app` passed 717 tests.

### VF-005
- Source: `sc-lang-python`
- Severity: Low
- Confidence: 92
- Title: Sandbox runner script indentation defect (control reliability issue)
- Decision: fix
- Owner: Platform security
- Target date: 2026-06-07
- Status: Fixed; regression covered, full security scan rerun pending
- Required evidence: sandbox runner unit test completed; full security scan rerun pending
- Files:
- `ai_data_science_team/utils/sandbox.py:346`
- Evidence:
- 2026-06-04 `python -m pytest tests/test_sandbox.py -q` passed 2 tests.
- 2026-06-04 `python -m pytest tests -q` passed 99 tests.
