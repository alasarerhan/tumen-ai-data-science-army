# ADR-0005: PostgreSQL as Primary Database

- Status: Accepted
- Date: 2026-03-30
- Owners: Platform Architecture

## Decision

PostgreSQL is the primary relational database for all platform data: tenants, users, workspaces, workflows, runs, artifacts metadata, chat sessions, and audit logs.

## Context

The platform requires:
- Multi-tenant data isolation with row-level security
- ACID compliance for workflow runs and audit logs
- Complex relational queries (tenant → workspace → user hierarchy)
- Full-text search capability for chat messages
- JSON support for flexible schema (workflow specs, artifact metadata)

## Alternatives Considered

1. **MongoDB (Document Store)**
   - Pros: Flexible schema, horizontal scaling, natural fit for JSON-heavy data
   - Cons: No native ACID for multi-document transactions, weaker JOIN support, additional operational complexity
   - Rejected: Relational integrity is critical for multi-tenant isolation

2. **PostgreSQL + MongoDB (Polyglot)**
   - Pros: Best of both worlds - relational for core, document for chat/artifacts
   - Cons: Dual database operations, data consistency challenges, increased complexity
   - Rejected: Premature for current scale; revisit if chat message volume exceeds 10M/month

3. **PostgreSQL only (Selected)**
   - Pros: Single operational surface, strong ecosystem, JSONB for flexibility, RLS for tenant isolation
   - Cons: Horizontal scaling requires more effort than NoSQL

## Consequences / Trade-offs

- Pros:
  - Single database to operate and backup
  - Native row-level security for tenant isolation
  - JSONB columns for flexible workflow spec storage
  - Strong ecosystem (Alembic migrations, SQLAlchemy ORM)
  - Full-text search via `tsvector` for chat messages
- Cons:
  - Chat message volume may require sharding or migration to NoSQL later
  - Artifact metadata at scale may benefit from document store
  - Read replicas needed for read-heavy workloads

## Rollback Cost Estimate

- High (3-4 weeks engineering):
  - Migrate chat messages to NoSQL
  - Update all services to dual-database pattern
  - Data migration scripts and validation

## Trigger Metrics

Re-evaluate this ADR if:
- Chat message count exceeds 10M records with >1000 inserts/minute
- Artifact metadata queries exceed 500ms p95
- Tenant data isolation requires database-per-tenant model

## Related

- ADR-0004: Centralized Tenant Quota (uses PostgreSQL advisory locks)
- Migration 0008: Tenant RLS policies
