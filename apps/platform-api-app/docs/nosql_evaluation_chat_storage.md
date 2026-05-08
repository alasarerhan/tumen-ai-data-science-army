# NoSQL Evaluation: Chat Message Storage

- Status: Evaluation Complete
- Date: 2026-03-30
- Owners: Platform Architecture

## Summary

**Recommendation: Keep PostgreSQL for chat messages at current scale.**

Re-evaluate when chat message volume exceeds thresholds defined below.

## Current State

| Metric | Current | Threshold for Re-evaluation |
|--------|---------|------------------------------|
| Chat messages/month | <100K | 10M/month |
| Messages per session | ~10-50 | >500/session |
| Insert rate | <100/minute | >1000/minute |
| Query latency p95 | <50ms | >200ms |

## Evaluation Criteria

### 1. Data Model Fit

| Aspect | PostgreSQL | MongoDB | DynamoDB |
|--------|------------|---------|----------|
| Message schema | JSONB flexible | Native JSON | Native JSON |
| Session relationship | Foreign key JOIN | Embed or reference | Reference only |
| Full-text search | `tsvector` native | Atlas Search | Limited |
| Schema evolution | Migration required | Flexible | Flexible |

**Assessment**: PostgreSQL JSONB provides sufficient flexibility. Session relationship benefits from relational model.

### 2. Query Patterns

| Query | PostgreSQL | MongoDB | DynamoDB |
|-------|------------|---------|----------|
| Get session messages | `WHERE session_id = ?` | `find({session_id})` | GSI required |
| Full-text search | `tsvector @@ query` | Atlas Search ($) | Limited |
| Recent sessions | `ORDER BY created_at DESC` | Index + sort | GSI + sort |
| Aggregate stats | `COUNT`, `GROUP BY` | Aggregation pipeline | Scan required |

**Assessment**: PostgreSQL handles all current query patterns efficiently.

### 3. Operational Complexity

| Factor | PostgreSQL | MongoDB | DynamoDB |
|--------|------------|---------|----------|
| Current ops | Already deployed | New cluster | New table |
| Backup/restore | Unified with app DB | Separate | Point-in-time |
| Monitoring | Unified | Separate | CloudWatch |
| Team expertise | High | Medium | Low |

**Assessment**: Adding NoSQL increases operational burden significantly.

### 4. Cost Analysis (Monthly, 10M messages)

| Option | Infrastructure | Operations | Total |
|--------|----------------|------------|-------|
| PostgreSQL (current) | $200 (included) | $0 | $200 |
| MongoDB Atlas | $300-500 | $200 | $500-700 |
| DynamoDB | $150 (on-demand) | $100 | $250 |

**Assessment**: PostgreSQL is most cost-effective at current scale.

## Migration Path (If Needed)

If thresholds are exceeded, migration to MongoDB would involve:

1. **Phase 1: Dual-Write (1 week)**
   - Write to both PostgreSQL and MongoDB
   - Read from PostgreSQL only

2. **Phase 2: Backfill (1 week)**
   - Migrate historical messages
   - Validate data integrity

3. **Phase 3: Read Migration (1 week)**
   - Switch reads to MongoDB
   - Monitor performance

4. **Phase 4: Deprecation (1 week)**
   - Stop writing to PostgreSQL
   - Remove old tables

**Total migration effort**: 4 weeks, 2 engineers

## Decision Matrix

| Criterion | Weight | PostgreSQL | MongoDB | DynamoDB |
|-----------|--------|------------|---------|----------|
| Query fit | 30% | 9/10 | 8/10 | 6/10 |
| Ops simplicity | 25% | 10/10 | 6/10 | 7/10 |
| Team expertise | 20% | 9/10 | 6/10 | 4/10 |
| Cost | 15% | 9/10 | 5/10 | 7/10 |
| Scalability | 10% | 6/10 | 9/10 | 10/10 |
| **Weighted Score** | | **8.8** | **6.7** | **6.5** |

## Conclusion

PostgreSQL remains the optimal choice for chat message storage at current scale. The JSONB column type provides schema flexibility, and the relational model supports session relationships naturally.

**Trigger for re-evaluation**:
- Chat message count exceeds 10M records
- Insert rate exceeds 1000/minute sustained
- Query latency exceeds 200ms p95

## Related

- ADR-0005: PostgreSQL as Primary Database
- `platform_api/db/models.py` - ChatSession, ChatMessage, ChatUpload
