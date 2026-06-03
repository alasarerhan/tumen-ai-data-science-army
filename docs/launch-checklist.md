# M20 GA Release Launch Checklist

> Status: Legacy template until rewritten with current owners, environment assumptions, and evidence.
>
> Do not treat this file as active release truth until the placeholders below are replaced or the checklist is superseded by a newer artifact under `docs/`.
>
> Active successor: `docs/release-readiness-checklist.md`

## Pre-Launch Timeline

### T-7 Days: Feature Freeze
- [ ] No new features merged to main
- [ ] All feature branches closed or deferred
- [ ] Product sign-off on feature completeness
- [ ] QA sign-off on feature testing

### T-5 Days: Bug Bash
- [ ] Critical bugs triaged and assigned
- [ ] Blocker bugs resolved
- [ ] Known issues documented

### T-3 Days: Code Freeze
- [ ] Only critical bug fixes allowed
- [ ] All PRs require 2 approvals
- [ ] No refactoring changes
- [ ] Dependencies locked

### T-2 Days: Documentation Freeze
- [ ] User documentation complete
- [ ] API documentation updated
- [ ] Runbooks reviewed and updated
- [ ] Release notes drafted

### T-1 Day: Go/No-Go Meeting

#### Go Criteria
- [ ] All CI gates passing (TG1-TG4)
- [ ] No critical bugs open
- [ ] Performance baselines met
- [ ] Security scan clean
- [ ] Documentation complete
- [ ] On-call rotation confirmed
- [ ] Rollback procedure tested

#### No-Go Triggers
- [ ] Critical bug unresolved
- [ ] CI gates failing
- [ ] Performance regression > 20%
- [ ] Security vulnerability found
- [ ] Key documentation missing

## Launch Day

### Pre-Launch
- [ ] War room opened (Slack channel + video call)
- [ ] On-call engineer confirmed
- [ ] Monitoring dashboards visible
- [ ] Rollback procedure ready

### Launch Sequence
1. [ ] Trigger canary deployment (5%)
2. [ ] Monitor for 1 hour
3. [ ] Check error rate < 1%
4. [ ] Check latency within baseline
5. [ ] Proceed to 25% if metrics OK
6. [ ] Monitor for 2 hours
7. [ ] Proceed to 50% if metrics OK
8. [ ] Monitor for 4 hours
9. [ ] Proceed to 100% if metrics OK

### Rollback Triggers
- Error rate > 1% for 5 minutes
- P95 latency > 2x baseline
- User-reported critical issues
- Manual trigger by on-call

## Post-Launch

### 24 Hours
- [ ] War room active
- [ ] Hourly metric check
- [ ] User feedback monitored
- [ ] Incident response ready

### 7 Days
- [ ] User adoption metrics
- [ ] Error trend analysis
- [ ] Performance trend analysis
- [ ] User satisfaction survey

### 14 Days
- [ ] Feature usage analysis
- [ ] Support ticket trends
- [ ] Performance optimization review

### 30 Days
- [ ] Full retrospective
- [ ] Documentation updates
- [ ] Process improvements identified

## Contacts

| Role | Name | Contact |
|------|------|---------|
| Release Lead | | |
| Frontend On-Call | | |
| Backend On-Call | | |
| Product Owner | | |
| Engineering Manager | | |

## Monitoring Links

- Sentry Dashboard: https://sentry.io/projects/[project]
- Performance Dashboard: [DataDog/Grafana URL]
- CI Dashboard: https://github.com/[org]/[repo]/actions
- Status Page: https://status.example.com
# Legacy Launch Checklist Template

> This file is not the active release source of truth. Use
> `docs/release-readiness-checklist.md` for current release evidence, owners,
> open risk, and go/no-go decisions.
