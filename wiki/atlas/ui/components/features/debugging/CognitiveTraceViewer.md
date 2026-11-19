---
title: CognitiveTraceViewer
type: atlas-component
path: frontend/src/components/features/debugging/CognitiveTraceViewer.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# CognitiveTraceViewer

**Path**: `frontend/src/components/features/debugging/CognitiveTraceViewer.tsx`
**Last Updated**: 2026-08-01

## Purpose

A comprehensive trace viewer for the cognitive pipeline (Phase 4: Polish + Observability — Task 1: Cognitive Trace Viewer). It renders a per-message breakdown of the four pipeline phases — `context_builder`, `executor`, `memory_manager`, `response_formatter` — including the strategy used, duration, token usage, metadata, and per-phase errors, plus whole-run summary metrics (total duration, total tokens, LLM calls, tool calls, cache hits) and memory-delta info (stored/evicted keys, compaction flag).

The component exposes two modes via tabs:

- **Live Stream** — subscribes to a server-sent events (SSE) stream via `EventSource` on `/api/v1/agent-chat/trace-stream`, listening for `cognitive_trace_complete` events. The stream auto-starts on mount and closes on unmount; the most recent 100 events are kept in memory. Each event renders as a `TraceCard` with expand/collapse detail and optional auto-scroll.
- **History** — fetches persisted traces from the database via `GET /api/v1/agent-chat/session/traces?limit=50`, rendered as a collapsible list of `TraceEntry` rows, each expanding into a summary card plus four phase step cards.

A component filter (`All Components` or one of the four phases) narrows both views to runs where the selected phase had non-zero duration or tokens. The component takes **no props** and is fully self-contained.

## Props Interface

The component is a default export that accepts **no props**:

```typescript
export default function CognitiveTraceViewer()
```

It consumes the following data shapes (copied verbatim from the source), which are what the backend SSE/fetch payloads must satisfy:

```typescript
interface ComponentTraceData {
  strategy: string
  duration_ms: number
  tokens_used: number
  metadata: Record<string, unknown>
  error: string | null
}

interface CognitiveTraceCompleteData {
  trace: {
    context_builder: ComponentTraceData
    executor: ComponentTraceData
    memory_manager: ComponentTraceData
    response_formatter: ComponentTraceData
    total_duration_ms: number
    total_tokens: number
  }
  metrics: {
    total_duration_ms: number
    total_tokens: number
    llm_calls: number
    tool_calls: number
    cache_hits: number
  }
  memory_delta: {
    stored_keys: string[]
    evicted_keys: string[]
    compaction_triggered: boolean
  } | null
  error: string | null
}

interface TraceEntry {
  id: number
  session_id: number
  message_id: number | null
  trace: CognitiveTraceCompleteData['trace']
  metrics: CognitiveTraceCompleteData['metrics']
  memory_delta: CognitiveTraceCompleteData['memory_delta']
  error: string | null
  created_at: string
}

type ComponentName = 'context_builder' | 'executor' | 'memory_manager' | 'response_formatter'
```

## Dependencies

| Dependency | Type | Purpose |
| --- | --- | --- |
| `useState`, `useEffect`, `useCallback`, `useRef` (React) | Hooks | Tab/stream/history/filter state; stream lifecycle (auto-start on mount, cleanup on unmount); refs to the `EventSource` and the live-scroll container |
| `frontendLoggingService` (`../../../services/frontendLoggingService`) | Service | Logs SSE parse failures (`frontendLoggingService.error('CognitiveTraceViewer', ...)`) |
| `EventSource` (browser API) | Native API | SSE live stream to `/api/v1/agent-chat/trace-stream`; `cognitive_trace_complete` events carry `CognitiveTraceCompleteData` JSON |
| `fetch` (browser API) | Native API | Loads history from `/api/v1/agent-chat/session/traces?limit=50` |

**Data source**: backend REST/SSE under `API_BASE = '/api/v1/agent-chat'`:
- Live: SSE stream `GET /api/v1/agent-chat/trace-stream`, event type `cognitive_trace_complete`.
- History: `GET /api/v1/agent-chat/session/traces?limit=50` → `{ traces: TraceEntry[] }`.

## Usage Example

The component is rendered without props inside the Debugging page's "Cognitive Traces" tab:

```tsx
import CognitiveTraceViewer from '../components/features/debugging/CognitiveTraceViewer'

// frontend/src/pages/Debugging.tsx — cognitive traces tab
{activeTab === 'cognitive' && (
  <div className="space-y-6">
    <CognitiveTraceViewer />
  </div>
)}
```

## State Used

All state is internal (no props, no external store):

| State | Type | Purpose |
| --- | --- | --- |
| `activeTab` | `'live' \| 'history'` | Switches between Live Stream and History views; history is fetched on tab entry |
| `liveEvents` | `CognitiveTraceCompleteData[]` | In-memory ring buffer of SSE events, capped at the last 100 |
| `isStreaming` / `streamError` | `boolean` / `string \| null` | Live-stream status and SSE connection error message |
| `eventSourceRef` | `useRef<EventSource \| null>` | Handle for the active `EventSource` (closed on stop/unmount) |
| `historyTraces` / `historyLoading` / `historyError` | `TraceEntry[]` / `boolean` / `string \| null` | History list, load indicator, and fetch error |
| `selectedTraceId` | `number \| null` | Which history entry is expanded (toggle) |
| `componentFilter` | `ComponentName \| 'all'` | Phase filter applied to both live and history views |
| `autoScroll` | `boolean` | Live view auto-scrolls to bottom on new events when enabled |
| `liveContainerRef` | `useRef<HTMLDivElement \| null>` | Scroll container for the live event list |

## Related Components

- `frontend/src/pages/Debugging.tsx` — hosts `<CognitiveTraceViewer />` in the "Cognitive Traces" tab alongside the other debugging tools.
- `frontend/src/components/features/agentInteraction/CognitiveTraceDebugOverlay.tsx` — sibling overlay in the agent-interaction area that surfaces the same cognitive-pipeline trace data during chat.
- `frontend/src/components/features/debugging/BackendTraceViewer.tsx` — sibling viewer on the Debugging page ("Agent Traces" tab) for raw agent-chat request traces.
- `frontend/src/components/features/debugging/LiveMonitoring.tsx`, `TraceAnalysis.tsx`, `TraceControls.tsx`, `DatabaseTools.tsx`, `LogViewer.tsx`, `SystemDiagnostics.tsx` — other tools on the same Debugging page.
- `frontend/src/services/frontendLoggingService.ts` — logging service used for SSE parse errors.
