# SECURITY REPORT

Scan date: 2026-04-09
Scan scope: `C:\Users\erhan\OneDrive\Desktop\ERHAN\AI_DATASCIENCE_TEAM`
Mode: Full scan (Recon -> Hunt -> Verify -> Report)

## Executive Summary
The repository includes strong baseline controls (CSRF middleware, CORS allowlist, OIDC validation, egress allowlist, path traversal checks), but there are high-impact weaknesses in generated-code execution and secret handling.

Risk score: 7.8 / 10 (High)

## Severity Breakdown
- Critical: 1
- High: 1
- Medium: 2
- Low: 1
- Total verified findings: 5

## Top Findings

### 1. Critical: Unsandboxed dynamic exec on SQL-agent path
- File: `ai-data-science-team/ai_data_science_team/templates/agent_templates.py:919`
- Risk: Generated code is executed in-process with access to high-capability globals and SQL connection context.
- Evidence: Reachable through `ai_data_science_team/agents/sql_database_agent.py:827`.

### 2. High: Exposed OpenAI API key in local .env files
- Files:
- `ai-data-science-team/.env:19`
- `ai-data-science-team/apps/platform-api-app/.env:19`
- Risk: Credential theft and billing/data exposure if local files leak.

### 3. Medium: CI supply-chain hardening gaps
- Files: `.github/workflows/*.yml`
- Risk: Actions not pinned to immutable SHAs; workflow token permissions not explicitly minimized.

### 4. Medium: Weak default DB credentials in deployment templates
- Files:
- `apps/platform-api-app/helm/platform/templates/secret-db.yaml:25`
- `apps/platform-api-app/helm/platform/values.yaml:165`
- `apps/platform-api-app/docker-compose.yml:5`

### 5. Low: Sandbox runner script has indentation defect
- File: `ai_data_science_team/utils/sandbox.py:346`
- Risk: Security control reliability degradation.

## Remediation Roadmap

### Phase A (Immediate, 24h)
1. Revoke and rotate exposed OpenAI key.
2. Replace key values in local `.env` files with placeholders.
3. Block unsafe SQL-agent exec path in production builds (feature flag or hard disable).

### Phase B (Short-term, 1 week)
1. Refactor SQL-agent execution to isolated sandbox process/container only.
2. Add unit/integration tests that assert sandboxed execution path works and rejects escape attempts.
3. Pin all GitHub Actions to commit SHAs.

### Phase C (Hardening, 2-3 weeks)
1. Enforce explicit GitHub Actions `permissions` per job.
2. Remove weak default DB credentials for non-local environments (chart validation gate).
3. Introduce secret scanning pre-commit and CI checks.

### Phase D (Continuous)
1. Schedule recurring dependency CVE scans (`pip-audit`, npm audit/SCA) in CI.
2. Add policy-as-code checks for IaC and workflow security baselines.

## Scan Limitations
- CVE database-backed dependency scan could not run in this environment because `pip_audit` and `safety` were not installed.
- Findings are based on static code/config analysis plus local behavior verification for selected execution paths.
