---
title: BackendTraceViewer
type: atlas-component
path: frontend/src/components/features/debugging/BackendTraceViewer.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---

# BackendTraceViewer

**Path**: `frontend/src/components/features/debugging/BackendTraceViewer.tsx`
**Last Updated**: 2026-08-01

## Purpose

Backend trace viewer for the debugging UI. Fetches and displays **execution traces** recorded by the backend cognitive pipeline (request traces: one summary row per pipeline run, expandable to the individual observations/spans inside that run). It shows a filterable trace list (time, mode, session, duration, observation count, warning count) and a drill-down detail table of trace observations (name, kind, duration, level, status message). Data comes from a **real backend API** — the component fetches JSON from `/api/v1/traces/...` via the browser `fetch` API; it does not use simulated/mock data.

## Props Interface

Props are declared inline on the function signature (no named interface):

```typescript
export default function BackendTraceViewer({ defaultSource, title, sourceLabel }: {
  defaultSource?: string
  title?: string
  sourceLabel?: string
})
```

| Prop | Type | Default | Purpose |
| --- | --- | --- | --- |
| `defaultSource` | `string \| undefined` | `undefined` | Passed as the `source` query parameter on the initial trace fetch, filtering traces by pipeline source. |
| `title` | `string \| undefined` | built-in default heading | Heading text rendered in an `<h3>`; a built-in label ("... Request Traces") is used when omitted. |
| `sourceLabel` | `string \| undefined` | built-in default description | Descriptive paragraph under the heading; a built-in label ("Recent traces from the cognitive pipeline.") is used when omitted. |

## Dependencies

| Dependency | Type | Purpose |
| --- | --- | --- |
| `useState` | React hook | Local state for `traces`, `selectedTrace`, `traceDetail`, `loading`, `error`, `sessionFilter`. |
| `useEffect` | React hook | Triggers the initial `fetchTraces(undefined, defaultSource)` on mount and whenever `defaultSource` changes. |
| `fetch` | Browser Web API | Real HTTP calls to the backend trace API (`/api/v1/traces/traces?limit=50` and `/api/v1/traces/traces/{trace_id}`). |

No external stores, services, or state-management libraries are used.

## Data Source (API)

- Base: `API_BASE = "/api/v1/traces"` (relative URL, same-origin backend).
- List: `GET {API_BASE}/traces?limit=50` with optional `&session_id=<id>` and `&source=<source>`; response shape `{ traces: TraceSummary[] }`.
- Detail: `GET {API_BASE}/traces/{trace_id}`; response shape `{ observations: TraceObservation[] }`.

Data contracts (defined locally in the file):

```typescript
interface TraceSummary {
  trace_id: string
  name: string
  session_id: string | null
  mode: string | null
  started_at: number      // seconds since epoch
  duration_ms: number
  observation_count: number
  warning_count: number
  tags: string[]
}

interface TraceObservation {
  id: string
  name: string
  kind: string
  trace_id: string
  parent_id: string | null
  started_at: number
  duration_ms: number | null
  level: string           // e.g. "ERROR", "WARNING"
  status_message: string | null
  metadata: Record<string, unknown>
  mode: string | null
}
```

## Usage Example

```tsx
import BackendTraceViewer from "@/components/features/debugging/BackendTraceViewer"

// Inside a debugging page:
<BackendTraceViewer
  defaultSource="cognitive-pipeline"
  title="Pipeline Traces"
  sourceLabel="Recent execution traces from the cognitive pipeline."
/>

// Minimal usage — all props optional:
<BackendTraceViewer />
```

## State Used

| State | Type | Initial | Purpose |
| --- | --- | --- | --- |
| `traces` | `TraceSummary[]` | `[]` | Trace summary rows from the list endpoint. |
| `selectedTrace` | `string \| null` | `null` | `trace_id` of the row clicked; also highlighted in the list. |
| `traceDetail` | `TraceObservation[] \| null` | `null` | Observations for the selected trace; `null` while a detail fetch is in flight. |
| `loading` | `boolean` | `true` | True while the trace list is being fetched. |
| `error` | `string \| null` | `null` | Error message from a failed list fetch, rendered in red. |
| `sessionFilter` | `string` | `""` | Session ID filter input; applied on Enter or via the Search/Clear buttons. |

## Related Components

- `frontend/src/components/features/debugging/CognitiveTraceViewer.tsx` — sibling trace viewer (client-side cognitive traces).
- `frontend/src/components/features/debugging/TraceAnalysis.tsx` — trace analysis tooling in the same debugging feature set.
- `frontend/src/components/features/debugging/TraceControls.tsx` — trace-related controls in the debugging UI.
- `frontend/src/components/features/debugging/LogViewer.tsx` — request/log viewing companion in the debugging folder.
- `frontend/src/components/features/debugging/DebugControls.tsx` — parent debugging toolbar that typically hosts feature panels like this viewer.
