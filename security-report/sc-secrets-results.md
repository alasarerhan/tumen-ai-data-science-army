# sc-secrets Results

## Finding: SEC-001
- Severity: High
- Confidence: 98
- CWE: CWE-798 (Use of Hard-coded Credentials)
- Title: Real OpenAI API key present in local environment files
- Evidence:
- `ai-data-science-team/.env:19`
- `ai-data-science-team/apps/platform-api-app/.env:19`
- Notes:
- The files are ignored by git, but keys still exist in plaintext on disk.
- Impact: Secret theft from endpoint compromise, backups, logs, or accidental sharing.
- Original remediation:
- Completed 2026-06-09: revoke/rotate owner attestation recorded.
- Completed 2026-06-09: local runtime secrets now live only in ignored repo-root `.env`; app-level env files are absent.
- Recommended production hardening: load runtime secrets from secure secret manager or OS keychain.

## 2026-06-09 Closure Update

- Status: Fixed for repo/release tracking.
- Owner attestation: credential owner added the rotated OpenAI project key to the single ignored repo-root `.env`.
- Repo hygiene evidence: `.env` is untracked, app-level env files are absent, and `python tools/secret_hygiene_scan.py` returned `No tracked OpenAI-style secret values found.`
- Provider liveness note: `/v1/models` status-only check was attempted without printing the secret, but this local environment returned `URLError`; provider availability is therefore not claimed from this scan.
