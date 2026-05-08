# ADR-0006: Prefect for Production Orchestration

- Status: Accepted
- Date: 2026-03-30
- Owners: Platform Architecture

## Decision

Prefect (self-hosted or Prefect Cloud) is the production workflow orchestration layer for scheduled runs, retries, queue management, and run history.

## Context

The platform needs:
- Reliable scheduling for automated workflow execution
- Retry logic with exponential backoff
- Queue management for concurrent run limits
- Run history and observability
- Integration with existing Python codebase

## Alternatives Considered

1. **Apache Airflow**
   - Pros: Mature, large community, extensive operator library
   - Cons: Heavy infrastructure (Postgres + Redis + Scheduler + Webserver), DAGs in Python files, steeper learning curve
   - Rejected: Overkill for current scale; Prefect's Python-native approach fits better

2. **Celery + Redis**
   - Pros: Lightweight, familiar to Python developers
   - Cons: No built-in scheduling UI, limited observability, manual retry logic
   - Rejected: Lacks first-class workflow concepts (dependencies, parameters, artifacts)

3. **Temporal**
   - Pros: Durable execution, complex workflow patterns
   - Cons: Requires separate server, Go/Java SDKs more mature than Python
   - Rejected: Python SDK less mature; overkill for current workflow complexity

4. **Prefect (Selected)**
   - Pros: Python-native, modern UI, Cloud option, lightweight self-hosting
   - Cons: Newer than Airflow, smaller community

## Consequences / Trade-offs

- Pros:
  - Python-native flow definitions match our codebase
  - Prefect Cloud option reduces operational burden
  - Built-in retry, caching, and result persistence
  - Clean separation: LangGraph for interactive, Prefect for production
- Cons:
  - Additional infrastructure dependency
  - Prefect Cloud requires external connectivity
  - Learning curve for team unfamiliar with Prefect

## Hybrid Orchestration Strategy

| Mode | Tool | Use Case |
|------|------|----------|
| Interactive | LangGraph | Chat-driven agent routing, real-time feedback |
| Production | Prefect | Scheduled runs, retries, queue management |

## Rollback Cost Estimate

- Medium (1-2 weeks engineering):
  - Migrate flows to Airflow or Celery
  - Update API orchestration gateway
  - Rebuild run history and observability

## Trigger Metrics

Re-evaluate this ADR if:
- Prefect Cloud SLA breaches exceed 0.1% monthly
- Self-hosted Prefect server requires >2 FTE for operations
- Flow execution latency exceeds 30s for simple workflows

## Related

- ADR-0001: Single Orchestration Path via `/v1/runs`
- `platform_api/orchestration/prefect_gateway.py`
