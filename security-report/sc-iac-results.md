# sc-iac Results

Status update: 2026-06-04 fixed with regression coverage; full security scan rerun remains pending.

## Finding: IAC-001
- Severity: Medium
- Confidence: 88
- CWE: CWE-1392 (Use of Default Credentials)
- Title: Weak database password defaults in deployment templates
- Evidence:
- `apps/platform-api-app/helm/platform/templates/secret-db.yaml:25` -> default `"changeme"`
- `apps/platform-api-app/helm/platform/values.yaml:165` -> bundled postgres password `"postgres"`
- `apps/platform-api-app/docker-compose.yml:5` -> `POSTGRES_PASSWORD: postgres`
- Impact: Misconfigured deployments can expose DB to trivial credential attacks.
- Remediation:
- Require non-default password input for all non-local profiles.
- Fail chart rendering/deployment when default secrets remain.
- Fix evidence: Helm DB secret templates now fail on empty/weak passwords, `values.yaml` ships empty password fields, docker compose requires `POSTGRES_PASSWORD`, and `tests/test_iac_secret_defaults.py` passed 4 tests on 2026-06-04.
