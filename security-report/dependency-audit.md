# Dependency Audit Report

## Discovery
- Node ecosystem detected:
- `frontend/package.json`
- `frontend/package-lock.json`
- Python ecosystem detected:
- `ai-data-science-team/requirements.txt`
- multiple app-level `requirements.txt` files
- `pyproject.toml` at repo root
- CI/dependency supply-chain surface:
- `.github/workflows/ci.yml`
- `.github/workflows/release-gates.yml`
- `.github/workflows/rollout.yml`

## Tooling Availability
- `pip_audit` not installed in scan environment.
- `safety` not installed in scan environment.
- No online advisory DB query was executed in this run.

## Findings

### Finding: DEP-001
- Severity: Medium
- Confidence: 90
- Package/Ecosystem: GitHub Actions ecosystem
- Vulnerability Type: Build Script Risk / Supply Chain
- Description: Workflows use floating action tags (`@v4`, `@v5`) instead of immutable commit SHAs.
- Evidence:
- `.github/workflows/ci.yml:53` (`actions/checkout@v4`)
- `.github/workflows/ci.yml:56` (`actions/setup-node@v4`)
- `.github/workflows/ci.yml:158` (`actions/setup-python@v5`)
- Similar patterns in `release-gates.yml` and `rollout.yml`.
- Impact: Upstream action tag compromise can affect CI execution.
- Remediation: Pin every action to a full commit SHA and periodically rotate via Dependabot/Renovate.

### Finding: DEP-002
- Severity: Medium
- Confidence: 85
- Package/Ecosystem: Python / PyPI
- Vulnerability Type: Dependency Drift / Reproducibility Risk
- Description: Main Python requirements are largely unpinned (e.g., `openai`, `pandas`, `sqlalchemy`, `streamlit` without fixed versions).
- Evidence: `ai-data-science-team/requirements.txt`.
- Impact: Uncontrolled upgrades increase exposure to supply-chain breakage and latent vulnerable releases.
- Remediation: Pin exact versions, maintain lock file(s), and run scheduled CVE audits.

## Dependency Audit Summary
- Total dependencies: Not fully resolved (lockfile absence in Python tree).
- Ecosystems scanned: npm, PyPI, GitHub Actions.
- Known CVEs confirmed: 0 (tooling unavailable for advisory lookup in this run).
- Supply-chain risks found: 2 (Medium: 2).
- Typosquatting risks: 0 confirmed.
- Dependency confusion risks: 0 confirmed.
- License concerns: Not assessed in this run.
- Outdated dependencies: Potentially present but not version-verified in this run.
