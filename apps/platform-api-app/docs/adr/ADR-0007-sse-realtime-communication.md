# ADR-0007: SSE for Real-Time Chat Streaming

- Status: Accepted
- Date: 2026-03-30
- Owners: Platform Architecture

## Decision

Server-Sent Events (SSE) is the transport for real-time chat message streaming from backend to frontend.

## Context

The AI Workspace feature requires:
- Streaming AI responses token-by-token for perceived latency
- Simple unidirectional communication (server → client)
- Automatic reconnection handling
- Compatibility with existing HTTP infrastructure

## Alternatives Considered

1. **WebSocket (Full Duplex)**
   - Pros: Bidirectional, lower latency for high-frequency messages
   - Cons: More complex state management, requires separate endpoint, proxy compatibility issues
   - Rejected: Unidirectional streaming is sufficient; WebSocket overhead unnecessary

2. **HTTP Polling**
   - Pros: Simplest implementation, works everywhere
   - Cons: Higher latency, unnecessary server load, poor UX
   - Rejected: Unacceptable latency for AI streaming experience

3. **SSE (Selected)**
   - Pros: Native browser support, simple HTTP, automatic reconnection, works through proxies
   - Cons: Unidirectional only, limited to text data
   - Selected: Matches use case perfectly

## Consequences / Trade-offs

- Pros:
  - Native `EventSource` API in browsers
  - Works through standard HTTP infrastructure (load balancers, proxies)
  - Automatic reconnection with `Last-Event-ID`
  - Simpler than WebSocket for server → client streaming
- Cons:
  - Unidirectional only (client cannot stream to server)
  - UTF-8 text only (no binary)
  - Connection limits vary by browser (6 per origin typically)

## Implementation Contract

```
POST /v1/chat/sessions/{id}/messages/stream
Response: Content-Type: text/event-stream

data: {"type": "delta", "delta": "Hello"}
data: {"type": "delta", "delta": " world"}
data: {"type": "message", "message": {...}}
data: {"type": "done"}
```

## Rollback Cost Estimate

- Low (<1 engineering day):
  - Replace SSE with WebSocket endpoint
  - Update frontend `useEventSource` hook to WebSocket

## Trigger Metrics

Re-evaluate this ADR if:
- Bidirectional streaming required (e.g., voice input streaming)
- Binary artifact streaming needed
- Connection limits become bottleneck (>6 concurrent streams per user)

## Related

- `frontend/src/app/hooks/useEventSource.ts`
- `platform_api/routes/chat.py` - `/sessions/{id}/messages/stream`
