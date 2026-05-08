# sc-iac Results

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
