# ADR-0003: Secure Auth Default (`AUTH_MODE=oidc`)

- Status: Accepted
- Date: 2026-03-23
- Owners: Platform Architecture + Security

## Decision

Authentication defaults are production-safe:
- `AUTH_MODE=oidc` by default.
- `AUTH_MODE=dev` is allowed only with `DEPLOYMENT_PROFILE=local`.
- Browser flows use cookie-first authentication with CSRF double-submit protection.
- `Authorization: Bearer` remains supported for automation/non-browser clients.

## Security Standard (Cookie-first + CSRF)

- Primary browser auth source: `HttpOnly` `access_token` cookie.
- CSRF token source: `GET /v1/auth/csrf` issues `csrf_token` cookie + JSON payload.
- State-changing methods (`POST/PUT/PATCH/DELETE`) require `X-CSRF-Token` when cookie auth is used.
- CSRF validation is bypassed only for configured exempt paths (health/metrics + auth bootstrap endpoints).

## Context

Dev-token auth was default, which created accidental insecure deployment risk when env setup drifted.

## Alternatives Considered

1. Keep `AUTH_MODE=dev` default and rely on deployment discipline.
2. Remove `dev` auth entirely.
3. Default to `oidc`, keep `dev` only for explicit local profile. (Selected)

## Consequences / Trade-offs

- Pros:
  - Safer out-of-the-box production behavior.
  - Clear profile-based policy boundary.
  - Reduces chance of silent insecure releases.
- Cons:
  - Local setup requires explicit profile env.
  - Misconfigured local profile now fails fast.

## Rollback Cost Estimate

- Low (<1 engineering day):
  - Revert defaults and remove profile guard.
  - Update tests/docs accordingly.

## Trigger Metrics

Revisit if:
- Local developer setup failure rate >10% for two consecutive sprints.
- Any production incident reports auth fallback pressure requiring broader dev-mode allowance.
