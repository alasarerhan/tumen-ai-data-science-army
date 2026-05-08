# Incident Response Playbook

## Severity Levels

| Level | Description | Response Time | Example |
|-------|-------------|---------------|---------|
| P1 | Data loss, security breach, complete outage | 5 minutes | Database deleted, credentials leaked |
| P2 | Service degraded, partial outage | 15 minutes | API 5xx errors > 5%, slow responses |
| P3 | Minor issues, single tenant affected | 1 hour | One user can't login, feature broken |

## Contacts

| Role | Contact |
|------|---------|
| On-call Engineer | #platform-oncall Slack |
| Platform Lead | @platform-lead |
| CTO | @cto (P1 escalation only) |

## Response Steps

### 1. Acknowledge (0-5 min)
- Post in #incidents: "INVESTIGATING: [brief description]"
- Create incident ticket if P1/P2

### 2. Investigate (5-30 min)
- Check Cloud Logging for errors
- Check /ready endpoint for health
- Review recent deployments
- Check external dependencies (Prefect, OpenAI)

### 3. Mitigate (30-60 min)
- If code issue: rollback deployment
  ```bash
  gcloud run services update-traffic platform-api --to-revisions=platform-api-previous=100
  ```
- If database issue: check DR plan for restore steps
- If external service: enable fallback mode

### 4. Resolve (1-4 hours)
- Deploy fix
- Verify with smoke tests
- Update incident ticket

### 5. Postmortem (within 48 hours)
- Write root cause analysis
- Document lessons learned
- Create follow-up tasks

## Customer Communication Templates

### Initial Response
```
We're aware of an issue affecting [service/feature]. 
Our team is investigating and will provide updates every 30 minutes.
Status: Investigating
```

### Update
```
Update: We've identified the issue as [brief description]. 
We're working on a fix. 
Next update in 30 minutes.
```

### Resolution
```
Resolved: The issue has been fixed. 
[Optional: brief explanation of what happened]
We apologize for any inconvenience.
```

## Quick Reference Commands

```bash
# Check API health
curl https://api.example.com/ready

# View recent logs
gcloud logging read "resource.type=cloud_run" --limit=100

# Rollback deployment
gcloud run services update-traffic platform-api --to-revisions=platform-api-previous=100

# Check database connections
gcloud sql connections list --instance=platform-db

# View current errors
gcloud logging read "severity>=ERROR" --limit=50
```

## Related Documents

- [Disaster Recovery Plan](./disaster_recovery_plan.md)
- [Architecture Decision Records](./adr/)
