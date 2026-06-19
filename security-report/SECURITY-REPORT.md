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
- Current status as of 2026-06-09: VF-001, VF-002, VF-004, and VF-005 are fixed with repo evidence; VF-003 is accepted risk for local/design-partner scope and remains GA hardening.

## Top Findings

### 1. Critical: Unsandboxed dynamic exec on SQL-agent path
- File: `ai-data-science-team/ai_data_science_team/templates/agent_templates.py:919`
- Risk: Generated code is executed in-process with access to high-capability globals and SQL connection context.
- Evidence: Reachable through `ai_data_science_team/agents/sql_database_agent.py:827`.
- Status: Fixed with direct read-only SQL execution and `tests/test_sql_agent_security.py`; full security scan rerun still pending.

### 2. High: Exposed OpenAI API key in local .env files
- Files:
- `ai-data-science-team/.env:19`
- `ai-data-science-team/apps/platform-api-app/.env:19`
- Risk: Credential theft and billing/data exposure if local files leak.
- Status: Fixed on 2026-06-09 by owner rotation attestation plus repo hygiene evidence. The replacement key is in the single ignored root `.env`; tracked secret scan is clean; app-level env files are absent. Provider liveness check was attempted but this environment returned `URLError`, so provider availability is not claimed.

### 3. Medium: CI supply-chain hardening gaps
- Files: `.github/workflows/*.yml`
- Risk: Actions not pinned to immutable SHAs; workflow token permissions not explicitly minimized.

### 4. Medium: Weak default DB credentials in deployment templates
- Files:
- `apps/platform-api-app/helm/platform/templates/secret-db.yaml:25`
- `apps/platform-api-app/helm/platform/values.yaml:165`
- `apps/platform-api-app/docker-compose.yml:5`
- Status: Fixed with fail-closed Helm password checks, required docker compose `POSTGRES_PASSWORD`, and `tests/test_iac_secret_defaults.py`; full security scan rerun still pending.

### 5. Low: Sandbox runner script has indentation defect
- File: `ai_data_science_team/utils/sandbox.py:346`
- Risk: Security control reliability degradation.
- Status: Fixed with `tests/test_sandbox.py`; full security scan rerun still pending.

## Remediation Roadmap

### Phase A (Immediate, 24h)
1. Done 2026-06-09: revoke/rotate owner attestation recorded for the exposed OpenAI key.
2. Done 2026-06-09: local env handling uses a single ignored repo-root `.env`; app-level env files are absent and tracked secret scan is clean.
3. Done 2026-06-04: SQL-agent generated-Python `exec` path removed from live connection execution; continue with full security scan rerun.

### Phase B (Short-term, 1 week)
1. Re-run security scan for the SQL-agent execution change and sandbox regression coverage.
2. Add broader integration coverage for SQL-agent dialect edge cases.
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
