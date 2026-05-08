# ADR-0001: Single Orchestration Path via `/v1/runs`

- Status: Accepted
- Date: 2026-03-23
- Owners: Platform Architecture

## Decision

`POST /v1/runs` is the single production orchestration contract.  
`/v1/prefect/*` remains compatibility-only for one minor version and is explicitly deprecated.

## Context

The system had two run-creation paths:
- `/v1/runs` creating `local-*` fake run ids
- `/v1/prefect/hello-runs` creating real Prefect flow runs

This split created contract drift and non-deterministic operational behavior.

## Alternatives Considered

1. Keep both paths active long-term.
2. Migrate fully to `/v1/prefect/*`.
3. Keep `/v1/runs` as canonical and absorb Prefect orchestration under it. (Selected)

## Consequences / Trade-offs

- Pros:
  - Single source of truth for run creation.
  - Clear API ownership and contract testing surface.
  - Easier rollout/retry/cancellation policy alignment.
- Cons:
  - Temporary compatibility layer maintenance for deprecated endpoints.
  - Requires deployment-id configuration in production environments.

## Rollback Cost Estimate

- Low to medium (1-2 engineering days):
  - Re-enable dual routing and undo deprecation behavior.
  - Revert run contract tests and API docs.

## Trigger Metrics

Re-evaluate this ADR if one of these is true:
- Deprecated `/v1/prefect/*` traffic remains >5% after one minor release.
- `POST /v1/runs` orchestration error rate >1% (5m rolling window).
- Mean run-creation latency regresses by >30% from baseline.
