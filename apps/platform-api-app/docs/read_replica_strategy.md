# Read Replica Strategy

- Status: Proposed
- Date: 2026-03-30
- Owners: Platform Architecture

## Summary

Read replicas are **not required at current scale**. This document defines the strategy for when and how to implement read replicas.

## Current State

| Metric | Current | Threshold for Read Replica |
|--------|---------|----------------------------|
| Read QPS | <100 | >1000 |
| Read latency p95 | <50ms | >200ms |
| DB CPU | <20% | >70% |
| Concurrent users | <100 | >1000 |

## When to Implement Read Replicas

Trigger implementation when **any** of the following is true:

1. Read query latency exceeds 200ms p95 for 7 consecutive days
2. Database CPU utilization exceeds 70% sustained
3. Read QPS exceeds 1000/second
4. Concurrent active users exceed 1000

## Architecture Options

### Option 1: Cloud SQL Read Replica (GCP)

```
┌─────────────┐     ┌─────────────┐
│   Primary   │────▶│ Read Replica│
│  (Writer)   │     │  (Reader)   │
└─────────────┘     └─────────────┘
      │                    │
      ▼                    ▼
┌─────────────┐     ┌─────────────┐
│   API       │     │   API       │
│  (writes)   │     │  (reads)    │
└─────────────┘     └─────────────┘
```

**Pros:**
- Managed by GCP
- Automatic failover
- Same VPC, low latency

**Cons:**
- Additional cost (~$100-300/month)
- Replication lag (typically <100ms)

### Option 2: Application-Level Caching (Redis)

```
┌─────────────┐
│   Primary   │
│  (Writer)   │
└─────────────┘
      │
      ▼
┌─────────────┐     ┌─────────────┐
│    Redis    │◀────│   API       │
│   (Cache)   │     │  (reads)    │
└─────────────┘     └─────────────┘
```

**Pros:**
- Lower cost
- Sub-millisecond latency
- Flexible caching strategies

**Cons:**
- Cache invalidation complexity
- Additional infrastructure
- Stale data risk

### Option 3: Hybrid (Read Replica + Redis)

For high-scale scenarios, combine both:

```
┌─────────────┐     ┌─────────────┐
│   Primary   │────▶│ Read Replica│
└─────────────┘     └─────────────┘
      │                    │
      ▼                    ▼
┌─────────────┐     ┌─────────────┐
│    Redis    │     │   API       │
│   (Cache)   │     │  (reads)    │
└─────────────┘     └─────────────┘
```

## Implementation Plan (When Triggered)

### Phase 1: Read Replica Setup (1 week)

1. Create Cloud SQL read replica
2. Add `READ_DATABASE_URL` environment variable
3. Configure SQLAlchemy with async engines for read/write splitting
4. Update services to use read replica for SELECT queries

### Phase 2: Application Changes (1 week)

```python
# Example: Read/write splitting in services
from platform_api.db.session import get_db, get_read_db

async def list_workspaces(db: Session = Depends(get_read_db)):
    # Uses read replica
    return db.query(Workspace).all()

async def create_workspace(db: Session = Depends(get_db)):
    # Uses primary
    db.add(workspace)
    db.commit()
```

### Phase 3: Monitoring (Ongoing)

- Track replication lag
- Monitor read replica query latency
- Alert on replica health

## Cost Estimate

| Option | Monthly Cost | Setup Effort |
|--------|--------------|--------------|
| Read Replica | $100-300 | 2 weeks |
| Redis Cache | $50-150 | 1 week |
| Hybrid | $150-450 | 3 weeks |

## Decision

**Do not implement now.** Re-evaluate when thresholds are met.

## Related

- ADR-0005: PostgreSQL as Primary Database
- `platform_api/db/session.py` - Database session management
