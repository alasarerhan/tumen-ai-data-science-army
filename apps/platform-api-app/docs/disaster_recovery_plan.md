# Disaster Recovery Plan

- Status: Proposed
- Date: 2026-03-30
- Owners: Platform Architecture + SRE

## Summary

This document defines the disaster recovery (DR) strategy for the AI Data Science Team platform.

## Recovery Time Objectives (RTO)

| Component | RTO | RPO |
|-----------|-----|-----|
| Platform API | 15 minutes | 0 (no data loss) |
| PostgreSQL | 1 hour | 5 minutes |
| Prefect | 30 minutes | 15 minutes |
| Artifacts (GCS) | 15 minutes | 0 |
| Frontend | 5 minutes | N/A |

## Failure Scenarios

### Scenario 1: Database Failure

**Symptoms:**
- Connection errors to PostgreSQL
- Query timeouts
- High CPU/memory on DB instance

**Recovery Steps:**

1. **Immediate (0-5 min):**
   - Check Cloud SQL dashboard for instance health
   - Review recent queries for blocking locks
   - Check if automatic failover triggered

2. **Short-term (5-30 min):**
   - If primary failed, Cloud SQL auto-failover to standby
   - If no standby, restore from point-in-time recovery (PITR)
   ```bash
   gcloud sql backups create --restore-instance=platform-db-restore \
     --source-instance=platform-db
   ```

3. **Validation (30-60 min):**
   - Run smoke tests: `python scripts/smoke_test.py`
   - Verify tenant isolation queries work
   - Check audit log integrity

### Scenario 2: API Service Failure

**Symptoms:**
- Health check failures
- 5xx error rate spike
- Container crashes

**Recovery Steps:**

1. **Immediate (0-5 min):**
   - Cloud Run auto-restarts failed containers
   - Check Cloud Logging for error patterns
   - Review recent deployments

2. **Rollback if needed (5-15 min):**
   ```bash
   gcloud run services update-traffic platform-api \
     --to-revisions=platform-api-previous=100
   ```

3. **Root cause (15-60 min):**
   - Analyze logs for exception patterns
   - Check dependency health (DB, Prefect, GCS)
   - Review recent code changes

### Scenario 3: Prefect Orchestration Failure

**Symptoms:**
- Workflow runs not starting
- Stuck in pending state
- Prefect API unreachable

**Recovery Steps:**

1. **Immediate (0-5 min):**
   - Check Prefect Cloud status page
   - Verify API key validity
   - Check network connectivity

2. **Failover (5-30 min):**
   - If Prefect Cloud down, switch to self-hosted:
   ```bash
   export PREFECT_API_URL=http://self-hosted-prefect:4200/api
   ```

3. **Recovery (30-60 min):**
   - Re-run failed flows from Prefect UI
   - Update run status in platform DB

### Scenario 4: Data Corruption

**Symptoms:**
- Invalid data in tables
- Missing records
- Constraint violations

**Recovery Steps:**

1. **Immediate (0-5 min):**
   - Stop writes to affected tables
   - Identify scope of corruption

2. **Restore (5-60 min):**
   - Point-in-time recovery to before corruption:
   ```bash
   gcloud sql backups create --restore-instance=platform-db-restore \
     --source-instance=platform-db \
     --restore-pitr-time="2026-03-30T10:00:00Z"
   ```

3. **Validation (60-120 min):**
   - Compare record counts before/after
   - Verify foreign key integrity
   - Run data validation queries

### Scenario 5: Region Outage

**Symptoms:**
- Complete region unavailable
- All services down

**Recovery Steps:**

1. **Immediate (0-15 min):**
   - Activate DR region (if configured)
   - Update DNS to DR endpoints

2. **Data Recovery (15-60 min):**
   - Restore PostgreSQL from cross-region backup
   - Sync artifacts from GCS cross-region replication

3. **Service Recovery (60-120 min):**
   - Deploy API to DR region
   - Update Prefect to use DR work pool
   - Verify all services operational

## Backup Strategy

| Component | Backup Method | Frequency | Retention |
|-----------|---------------|-----------|-----------|
| PostgreSQL | Cloud SQL automated backup | Every 6 hours | 30 days |
| PostgreSQL | Point-in-time recovery | Continuous | 7 days |
| Artifacts | GCS versioning | On write | 90 days |
| Workflow specs | DB backup + Git | On change | Indefinite |

## DR Testing Schedule

| Test | Frequency | Scope |
|------|-----------|-------|
| Backup restore drill | Monthly | Single table restore |
| Failover test | Quarterly | Primary → standby |
| Full DR drill | Annually | Complete region failover |

## Contact Escalation

| Level | Response Time | Contact |
|-------|---------------|---------|
| L1 | 5 minutes | On-call engineer |
| L2 | 15 minutes | Platform lead |
| L3 | 30 minutes | CTO |

## Related

- ADR-0005: PostgreSQL as Primary Database
- ADR-0008: Cloud Run Hardening Policy Baseline
- `scripts/smoke_test.py` - Health validation
