# Release Notes Template

Use this template for every design-partner or GA candidate release.

## Release Metadata

- Release name:
- Release type: design-partner | staging | GA candidate | GA
- Release date:
- Commit SHA:
- Branch:
- Owner:
- Approver:
- Rollback owner:

## Summary

Briefly describe the user-visible change, target users, and release intent.

## Shipped Changes

- Product:
- Frontend:
- Backend/API:
- Data/model/migrations:
- Security:
- Operations:
- Documentation:

## Public API and Contract Changes

- Added endpoints:
- Changed endpoints:
- Deprecated endpoints:
- Compatibility notes:

## Security and Privacy Notes

- Auth/session impact:
- Tenant/workspace isolation impact:
- Secret handling impact:
- Upload/artifact safety impact:
- Accepted/deferred findings:

## Test Evidence

| Gate | Command or evidence | Result | Notes |
|---|---|---|---|
| Frontend typecheck | | | |
| Frontend lint | | | |
| Frontend unit tests | | | |
| Backend tests | | | |
| Migration check | | | |
| Playwright golden path | | | |
| Smoke test | | | |
| Security regression | | | |

## Known Issues and Open Gates

- 

## Rollback Plan

- Rollback trigger:
- Rollback command/procedure:
- Data rollback/migration note:
- Verification after rollback:

## Monitoring and Support

- Dashboard:
- Alerts:
- Logs:
- On-call/contact:
- Incident doc:
