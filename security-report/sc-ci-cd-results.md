# sc-ci-cd Results

## Finding: CICD-001
- Severity: Medium
- Confidence: 90
- CWE: CWE-494 (Download of Code Without Integrity Check)
- Title: GitHub Actions are not pinned to immutable SHAs
- Evidence:
- `.github/workflows/ci.yml:53,56,91,107,158`
- `.github/workflows/release-gates.yml:21,23,56,58`
- `.github/workflows/rollout.yml:49`
- Impact: Compromised upstream action tags can alter CI behavior.
- Remediation: Pin actions to full commit SHAs and update through controlled automation.

## Finding: CICD-002
- Severity: Medium
- Confidence: 78
- CWE: CWE-250 (Execution with Unnecessary Privileges)
- Title: Workflow token permissions are not explicitly minimized
- Evidence:
- `.github/workflows/ci.yml` has no top-level or job-level `permissions:` block.
- Impact: Default `GITHUB_TOKEN` scopes may exceed least-privilege requirements.
- Remediation: Add explicit `permissions` (e.g., `contents: read`) per workflow/job.
