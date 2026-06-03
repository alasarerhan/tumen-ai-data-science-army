# Verified Findings

## Verification Summary
- Raw potential findings reviewed: 11
- Verified findings: 5
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
- Status: Open
- Required evidence: sandboxed execution regression test and changed-surface security rerun
- Files:
- `ai_data_science_team/templates/agent_templates.py:919`
- `ai_data_science_team/agents/sql_database_agent.py:827`
- Notes: Verified with local proof-of-behavior against helper execution path.

### VF-002
- Source: `sc-secrets`
- Severity: High
- Confidence: 98
- Title: Real OpenAI key in local .env files
- Decision: fix
- Owner: Platform operations
- Target date: 2026-06-05
- Status: Open
- Required evidence: key revoked/rotated, local `.env` untracked/clean, and secret scan rerun
- Files:
- `.env:19`
- `apps/platform-api-app/.env:19`

### VF-003
- Source: `sc-ci-cd`
- Severity: Medium
- Confidence: 90
- Title: Unpinned GitHub Actions tags
- Decision: defer
- Owner: DevOps
- Target date: 2026-06-14
- Status: Open
- Required evidence: pinned action SHAs or accepted-risk record
- Files:
- `.github/workflows/ci.yml:53`
- `.github/workflows/release-gates.yml:21`
- `.github/workflows/rollout.yml:49`

### VF-004
- Source: `sc-iac`
- Severity: Medium
- Confidence: 88
- Title: Weak default DB secrets in IaC/dev deployment templates
- Decision: fix
- Owner: Platform operations
- Target date: 2026-06-10
- Status: Open
- Required evidence: non-default secret generation path and deployment template regression check
- Files:
- `apps/platform-api-app/helm/platform/templates/secret-db.yaml:25`
- `apps/platform-api-app/helm/platform/values.yaml:165`
- `apps/platform-api-app/docker-compose.yml:5`

### VF-005
- Source: `sc-lang-python`
- Severity: Low
- Confidence: 92
- Title: Sandbox runner script indentation defect (control reliability issue)
- Decision: fix
- Owner: Platform security
- Target date: 2026-06-07
- Status: Open
- Required evidence: sandbox runner unit test and security scan rerun
- Files:
- `ai_data_science_team/utils/sandbox.py:346`
