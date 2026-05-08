# sc-docker Results

## Finding: DOCKER-001
- Severity: Low
- Confidence: 76
- CWE: CWE-250 (Execution with Unnecessary Privileges)
- Title: Container image does not declare non-root runtime user
- Evidence:
- `apps/platform-api-app/Dockerfile` has no `USER` directive.
- Impact: Container breakout or runtime exploit impact is higher under root.
- Remediation: Add non-root user, chown app files, and run final stage as that user.
