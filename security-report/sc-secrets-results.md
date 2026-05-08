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
- Remediation:
- Revoke and rotate exposed key immediately.
- Replace with placeholder values in local files.
- Load runtime secrets from secure secret manager or OS keychain.
