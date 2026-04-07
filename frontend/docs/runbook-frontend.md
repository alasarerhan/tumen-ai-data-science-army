# Frontend Runbook (M10)

## Overview
This runbook covers operational procedures for the Frontend application.

## Monitoring

### Error Tracking
- Sentry dashboard: https://sentry.io/projects/[project-id]
- Error rate threshold: > 1% of sessions
- Alert channel: #alerts-frontend (Slack)

### Performance Metrics
- Web Vitals dashboard: [Vitals endpoint]
- Key metrics:
  - LCP (Largest Contentful Paint): < 2.5s
  - FID (First Input Delay): < 100ms
  - CLS (Cumulative Layout Shift): < 0.1

## Common Issues

### High Error Rate
1. Check Sentry for recent errors
2. Identify error patterns (component, route, browser)
3. Check recent deployments
4. Rollback if necessary (see Rollback Procedures)

### Performance Degradation
1. Check Web Vitals dashboard
2. Identify slow routes/components
3. Check bundle size (should be < 500KB gzipped)
4. Review recent changes for performance regressions

## Rollback Procedures

### Frontend Rollback (CDN)
```bash
# 1. Identify previous version
git log --oneline -10

# 2. Trigger rollback deployment
npm run deploy:rollback -- --version=[previous-version]

# 3. Verify rollback
curl -I https://app.example.com | grep x-deploy-version
```

### Emergency Rollback
1. Access CDN dashboard
2. Select "Rollback to previous version"
3. Confirm rollback
4. Monitor error rates for 15 minutes

## On-Call Procedures

### Severity Levels
- P1: Site down or critical functionality broken
- P2: Significant feature broken, workaround exists
- P3: Minor issue, no immediate impact

### Escalation Path
1. Frontend on-call engineer
2. Frontend team lead
3. Engineering manager

## Health Checks

### Manual Health Check
- [ ] Login page loads
- [ ] Dashboard renders
- [ ] Workflow designer accessible
- [ ] API calls succeed (check Network tab)

### Automated Health Check
- Endpoint: /health
- Expected: 200 OK with { status: "ok" }
