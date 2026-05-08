# ADR-0002: Canonical Health Endpoint is `/healthz`

- Status: Accepted
- Date: 2026-03-23
- Owners: Platform Architecture

## Decision

`GET /healthz` is canonical for liveness/readiness probes.  
`GET /health` is a temporary alias for backward compatibility and scheduled for removal after one minor release.

## Context

Runtime probes and tests were mismatched:
- API exposed `/healthz`
- Helm probes still targeted `/health`

This mismatch risks false-negative readiness and unstable rollouts.

## Alternatives Considered

1. Keep `/health` canonical and remove `/healthz`.
2. Keep both forever.
3. Standardize on `/healthz` with a time-limited alias. (Selected)

## Consequences / Trade-offs

- Pros:
  - Probe configuration aligned with implemented endpoint.
  - Lower deployment failure risk due to path drift.
  - Clear, explicit health contract.
- Cons:
  - Temporary duplicate endpoint maintenance.
  - Requires deprecation communication to clients and ops teams.

## Rollback Cost Estimate

- Low (<1 engineering day):
  - Switch probe paths and API docs back to `/health`.

## Trigger Metrics

Re-open the decision if:
- Probe-related restart events increase >20% after rollout.
- Requests to alias `/health` remain >10% beyond one minor release.
