# ADR-0004: Centralized Tenant Quota with Database-backed Window

- Status: Accepted
- Date: 2026-03-23
- Owners: Platform Architecture

## Decision

Tenant write quota moved from process memory to centralized database events:
- New table: `tenant_quota_events`
- Sliding one-minute window enforcement
- PostgreSQL advisory lock per tenant for cross-replica consistency

## Context

In-memory per-process quota counters were inconsistent across replicas and could over-accept writes under scale-out.

## Alternatives Considered

1. Keep in-memory quota and rely on sticky routing.
2. Move to Redis distributed counters.
3. Use PostgreSQL event table + per-tenant lock. (Selected)

## Consequences / Trade-offs

- Pros:
  - Replica-consistent quota semantics.
  - No additional external datastore in short term.
  - Operationally simple for current stack.
- Cons:
  - Extra DB writes for each quota-guarded operation.
  - Periodic cleanup/delete overhead.
  - Advisory-lock contention possible for high single-tenant bursts.

## Rollback Cost Estimate

- Medium (2-3 engineering days):
  - Reintroduce in-memory path and feature-flag the DB strategy.
  - Remove migration and quota event queries from hot path.

## Trigger Metrics

Re-evaluate if:
- Quota-check p95 latency >20ms sustained.
- DB CPU increase attributable to quota table >10%.
- Lock wait time for tenant quota checks exceeds 200ms p95.
