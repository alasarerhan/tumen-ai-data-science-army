# Cloud Run Hardening Package (M8)

> Consolidated Cloud Run production hardening package: checklist, decision/evidence matrix, and policy ADR.
> Replaces `planning_docs/strategy_execution/cloud_run_hardening_checklist.md`, `planning_docs/strategy_execution/m8_cloud_run_decision_evidence.md`, and `planning_docs/strategy_execution/adr/ADR-0008-cloud-run-hardening-policy-baseline.md`.

**Original date:** 2026-03-09 (ADR) / 2026-03-23 (checklist + evidence).
**Status:** Decision package complete; technical rollout blocked by policy approvals.

## ADR-0008 — Cloud Run Hardening Policy Baseline

- **Status:** Proposed (awaiting approval).
- **Context:** M8 Cloud Run hardening requires governance approvals before implementation.

### Context

Platform API is ready for production hardening, but network/auth/secret/deploy policies require explicit enterprise approval. Running technical changes before policy alignment creates compliance risk and rollback uncertainty.

### Decision

Adopt the following policy baseline before executing M8 tasks:

1. **Network**: private ingress and controlled egress path.
2. **Auth**: IAM-protected Cloud Run service, no unauthenticated invocations.
3. **Secrets**: Secret Manager-backed runtime injection only.
4. **Deploy**: no-traffic revision deployment with staged traffic shifts (10/50/100).
5. **Rollback**: revision-based rollback drill must be proven before GA.

### Consequences

**Positive:**

- Reduces unauthorized access and secret leakage risk.
- Creates deterministic rollout/rollback behavior.
- Aligns with PR2/PR3/PR4 expectations.

**Trade-offs:**

- Introduces approval lead time.
- Requires additional evidence artifacts from SRE/Security.

### Approval Required

- Security team approval for ingress/auth/secret controls.
- SRE approval for rollout/rollback gate.
- Platform owner sign-off for runtime service account policy.

## Hardening Checklist

### Scope

Production readiness checklist for deploying `apps/platform-api-app` to GCP Cloud Run with Cloud SQL + Secret Manager.

### Prerequisites

- GCP project selected and billing enabled
- Cloud Run, Artifact Registry, Secret Manager, Cloud SQL APIs enabled
- Service account for runtime (least privilege)

### Build & Registry

- [ ] Build container image from `apps/platform-api-app/Dockerfile`
- [ ] Push image to Artifact Registry
- [ ] Tag image with immutable version (`git sha` or release tag)

### Secrets & Config

- [ ] Store `DATABASE_URL` (or parts) in Secret Manager
- [ ] Store `PREFECT_API_URL` and `PREFECT_API_KEY` in Secret Manager
- [ ] Store `OIDC_ISSUER`, `OIDC_AUDIENCE`, `OIDC_JWKS_URL` as env/secrets
- [ ] Set `AUTH_MODE=oidc` in production
- [ ] Set `PYTHONUNBUFFERED=1`

### Networking & DB

- [ ] Provision Cloud SQL (Postgres)
- [ ] Configure Cloud SQL connectivity for Cloud Run (connector or private path)
- [ ] Ensure DB user has minimum required permissions
- [ ] Run `alembic upgrade head` successfully against production DB

### Runtime Hardening

- [ ] Set minimum instances based on latency/SLA
- [ ] Set maximum instances to cap spend
- [ ] Set request timeout and concurrency explicitly
- [ ] Set CPU/memory limits intentionally
- [ ] Disable unauthenticated invocations unless explicitly needed

### Observability

- [ ] Structured JSON logs verified in Cloud Logging
- [ ] Error-rate alerting configured
- [ ] Latency P95 alerting configured
- [ ] Dashboard includes: request count, error count, latency, instance count

### Release & Rollback

- [ ] Deploy new revision with no traffic
- [ ] Execute smoke checks (`/healthz`, `/v1/me`, provisioning, runs, artifacts)
- [ ] Shift traffic gradually (e.g., 10% → 50% → 100%)
- [ ] Rollback plan validated (route traffic to previous healthy revision)

### Post-Deploy Validation

- [ ] `GET /healthz` returns `ok`
- [ ] OIDC token auth works on `/v1/me`
- [ ] Tenant/workspace isolation checks pass
- [ ] Prefect integration path verified (hello run create/read)
- [ ] Artifact access endpoint enforces workspace membership

## Decision & Evidence Matrix

| Area | Required Decision | Proposed Baseline | Evidence Artifact | Owner | Status |
|---|---|---|---|---|---|
| Network ingress | Public vs private ingress | Private ingress only, allowlist via gateway | `cloud_run_hardening_checklist.md` + VPC design doc | Platform + Security | Pending approval |
| Service auth | Unauthenticated vs IAM protected | Disable unauthenticated invocation | Cloud Run IAM policy export | Security | Pending approval |
| Runtime identity | Service account scope | Dedicated least-privilege runtime SA | IAM role binding report | Platform | Pending approval |
| Secret policy | Env var vs Secret Manager mount | Secret Manager references only | Secret inventory + rotation schedule | Security | Pending approval |
| DB access | Public IP vs private connector | Private connectivity to Cloud SQL | Connectivity test logs | Platform | Pending approval |
| Deploy strategy | Direct promote vs canary | No-traffic deploy then 10/50/100 rollout | Rollout audit log | SRE | Pending approval |
| Rollback | Manual patch vs revision switch | Traffic switch to last healthy revision | Rollback drill output | SRE | Pending approval |
| Observability | Basic logs vs SLO gates | Error-rate + p95 alerts required | Dashboard screenshots + alert policy IDs | SRE | Pending approval |

## Evidence Register (Ready for Attachment)

| Evidence Item | Target Artifact | Owner | Current State |
|---|---|---|---|
| IAM export | `gcloud run services get-iam-policy` output | Security | Not attached (approval gate pending) |
| Secret rotation policy | Rotation schedule and secret list | Security | Not attached (approval gate pending) |
| VPC egress policy | Network policy document | Platform | Not attached (approval gate pending) |
| Cloud SQL private path validation | Connection test logs | Platform | Not attached (approval gate pending) |
| Canary and rollback rehearsal | Rollout/rollback command logs | SRE | Not attached (approval gate pending) |
| Alert ownership map | Alert policy IDs + on-call rotation | SRE | Not attached (approval gate pending) |

## Blocker Summary

M8 remains intentionally blocked until Security/SRE/Platform policy approvals are signed. No production mutation is part of this iteration.

## Exit Criteria for Unblock

1. Approval signatures recorded for network/auth/secret/deploy policies.
2. Evidence register fully attached.
3. `m8_ready_to_execute_tasks.md` executed in release environment.

---

**Source consolidation note**

- `planning_docs/strategy_execution/adr/ADR-0008-cloud-run-hardening-policy-baseline.md` → §ADR-0008 (context, decision, consequences, approval).
- `planning_docs/strategy_execution/cloud_run_hardening_checklist.md` → §Hardening Checklist (all subsections).
- `planning_docs/strategy_execution/m8_cloud_run_decision_evidence.md` → §Decision & Evidence Matrix, §Evidence Register, §Blocker Summary, §Exit Criteria for Unblock.
