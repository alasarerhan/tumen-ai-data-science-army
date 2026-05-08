# ADR-0009: LangGraph for Agent Orchestration

- Status: Accepted
- Date: 2026-03-30
- Owners: Platform Architecture

## Decision

LangGraph is the framework for building and orchestrating AI agents in interactive (chat-driven) workflows.

## Context

The platform requires:
- Multi-agent collaboration (Pandas Analyst, SQL Analyst, Forecast, etc.)
- Stateful conversation management
- Tool calling and routing between agents
- Human-in-the-loop intervention points
- Integration with LangChain ecosystem

## Alternatives Considered

1. **CrewAI**
   - Pros: High-level abstractions, role-based agent design
   - Cons: Less control over state, limited tool integration, newer ecosystem
   - Rejected: Less mature; LangGraph's graph-based approach offers more control

2. **AutoGen (Microsoft)**
   - Pros: Multi-agent conversations, research backing
   - Cons: Complex setup, less Pythonic, heavier dependencies
   - Rejected: Overkill for current agent complexity

3. **Custom State Machine**
   - Pros: Full control, no external dependencies
   - Cons: Reinventing the wheel, no ecosystem, maintenance burden
   - Rejected: LangGraph already provides battle-tested patterns

4. **LangGraph (Selected)**
   - Pros: Graph-based state machine, LangChain integration, tool-aware routing
   - Cons: Learning curve, graph visualization limited

## Consequences / Trade-offs

- Pros:
  - Native LangChain tool integration
  - Graph-based state management (clearer than chain-of-thought)
  - Supervisor pattern for agent routing
  - Built-in persistence and checkpointing
  - Active development and community
- Cons:
  - Graph complexity can grow quickly
  - Debugging multi-step agent flows is challenging
  - Version compatibility with LangChain core

## Hybrid Orchestration (Reiterated)

| Layer | Tool | Responsibility |
|-------|------|----------------|
| Agent Logic | LangGraph | Tool selection, state transitions, routing |
| Production Runs | Prefect | Scheduling, retries, queue, history |
| API Gateway | FastAPI | Auth, tenant context, request routing |

## Rollback Cost Estimate

- High (2-3 weeks engineering):
  - Rewrite agent orchestration in CrewAI or custom
  - Update all agent definitions
  - Retest multi-agent workflows

## Trigger Metrics

Re-evaluate this ADR if:
- LangGraph introduces breaking changes without migration path
- Agent graph complexity exceeds maintainability threshold (>20 nodes)
- Alternative framework provides significant UX/performance gains

## Related

- `ai_data_science_team/multiagents/supervisor_ds_team.py`
- `ai_data_science_team/orchestration.py`
- STRATEGY.md Section 2.3: Mimari Prensipler
