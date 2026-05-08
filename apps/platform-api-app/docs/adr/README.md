# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for the Platform API.

## Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [ADR-0001](ADR-0001-orchestration-single-path.md) | Single Orchestration Path via `/v1/runs` | Accepted | 2026-03-23 |
| [ADR-0002](ADR-0002-health-contract-healthz.md) | Canonical Health Endpoint is `/healthz` | Accepted | 2026-03-23 |
| [ADR-0003](ADR-0003-auth-default-oidc.md) | Secure Auth Default (`AUTH_MODE=oidc`) | Accepted | 2026-03-23 |
| [ADR-0004](ADR-0004-centralized-tenant-quota.md) | Centralized Tenant Quota with Database-backed Window | Accepted | 2026-03-23 |
| [ADR-0005](ADR-0005-postgres-primary-database.md) | PostgreSQL as Primary Database | Accepted | 2026-03-30 |
| [ADR-0006](ADR-0006-prefect-orchestration.md) | Prefect for Production Orchestration | Accepted | 2026-03-30 |
| [ADR-0007](ADR-0007-sse-realtime-communication.md) | SSE for Real-Time Chat Streaming | Accepted | 2026-03-30 |
| [ADR-0008](../../../../planning_docs/strategy_execution/adr/ADR-0008-cloud-run-hardening-policy-baseline.md) | Cloud Run Hardening Policy Baseline | Proposed | 2026-03-09 |
| [ADR-0009](ADR-0009-langgraph-agent-framework.md) | LangGraph for Agent Orchestration | Accepted | 2026-03-30 |

## Creating a New ADR

1. Copy the template below
2. Name it `ADR-NNNN-short-title.md` (next number in sequence)
3. Fill in all sections
4. Update this README index

## ADR Template

```markdown
# ADR-NNNN: [Short Title]

- Status: [Proposed | Accepted | Deprecated | Superseded]
- Date: YYYY-MM-DD
- Owners: [Team/Person]

## Decision

[What is the decision?]

## Context

[Why is this decision needed? What is the problem?]

## Alternatives Considered

1. [Alternative 1]
   - Pros: ...
   - Cons: ...
   - [Selected | Rejected]: Reason

## Consequences / Trade-offs

- Pros: ...
- Cons: ...

## Rollback Cost Estimate

- [Low | Medium | High] (X engineering days):
  - What would be required to reverse this decision

## Trigger Metrics

Re-evaluate this ADR if:
- [Metric or condition that would prompt reconsideration]
```
