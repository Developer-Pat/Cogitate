---
title: TraceAnalysis
type: atlas-component
path: frontend/src/components/features/debugging/TraceAnalysis.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---

# TraceAnalysis

**Path**: `frontend/src/components/features/debugging/TraceAnalysis.tsx`
**Last Updated**: 2026-08-01

## Purpose

TraceAnalysis is the largest component in the debugging feature set (837 lines). It is a real-time trace viewer and analysis tool for **FlowTrace** logs emitted by the cognitive pipeline / agent flows. It fetches recent trace logs from the backend API (`GET /api/v1/logs/recent?source=FlowTrace`), transforms each raw log record into a `TraceEntry` (parsing `flow` and `step` out of the log message prefix `[prefix] Flow:Step(...)`), and renders them as a filterable, scrollable timeline.

Analysis features:

- **Timeline list**: each trace renders as a card with a sequence badge, `flow:step` identifier, formatted timestamp, relative "time ago", and a delta-from-previous-trace timing (+μs/ms/s) when high-precision `perfTime` is available.
- **Live auto-refresh**: polls the API every `refreshInterval` ms, but only while the container element is on screen (`IntersectionObserver`) and auto-refresh is enabled.
- **Filtering**: flow name substring, step search, sequence range, time range, tag selection (ANY-of semantics), and include/exclude free-text (comma-delimited, OR logic matched against message/flow/step).
- **Presets**: include presets (Chat Flows, Session Flows, Agent Flows, Errors Only) and exclude presets (System Noise, Background Tasks, Notifications, All Noise) that pre-fill the include/exclude text filters.
- **Tag/flow aggregation**: per-tag counts on the tag filter buttons and per-flow counts in the summary header, computed by `calculateStats`.
- **Expandable context inspection**: each trace's `context` object can be expanded, pretty-printed, and copied to the clipboard (Copy Context / Copy Trace).
- **Export**: downloads the currently loaded traces as JSON or CSV through the backend export endpoint.

The component does **not** use the frontend `TraceService` client (its `trace()` calls are commented out to avoid log noise); it reads traces back from the backend API. The trace data comes from the `FlowTrace` log source defined in `TraceService` (`frontend/src/services/domain/TraceService.ts`), which is emitted by chat, session, and agent flows of the cognitive pipeline.

## Props Interface

```typescript
interface TraceAnalysisProps {
  onExport?: (format: 'json' | 'csv') => void
  refreshInterval?: number
  initialLimit?: number
}
```

Defaults applied via destructuring: `refreshInterval = 2000` (ms between auto-refresh polls) and `initialLimit = 500` (number of most-recent traces fetched per load).

Internal data structures (defined in the same file):

```typescript
interface TraceEntry {
  sequence: number
  timestamp: string
  flow: string
  step: string
  message: string
  context: Record<string, unknown>
  tags?: TraceTag[]
  perfTime?: number  // High-precision time in ms since page load
}

interface TraceFilters {
  flowName?: string
  sequenceFrom?: number
  sequenceTo?: number
  stepSearch?: string
  timeFrom?: string
  timeTo?: string
  selectedTags?: TraceTag[]
  includeText?: string  // Include traces containing this text (comma-delimited, OR logic)
  excludeText?: string  // Exclude traces containing this text (comma-delimited, OR logic)
  includePreset?: string  // Selected preset inclusion pattern
}
```

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `useState`, `useEffect`, `useRef` | React hooks | Traces/filters/stats state; initial load + auto-refresh effects; visibility ref |
| `ErrorBoundary` | Component (`../../ErrorBoundary`) | Wraps the whole tree so a rendering error in a trace card cannot crash the page |
| `frontendLoggingService` | Service (`../../../services/frontendLoggingService`) | Logs load errors, export results, filter changes, and clipboard copies |
| `TraceTag` | Type (`../../../services/domain/TraceService`) | Tag union: lifecycle, data, api-call, streaming, error, performance, user-action, state-change, validation, cache, sync |
| `fetch` (backend API) | Browser API | Load: `GET {baseUrl}/api/v1/logs/recent?n={initialLimit}&source=FlowTrace`; Export: `GET {baseUrl}/api/v1/logs/traces/export?format=&limit=&flow=` (blob download) |
| `IntersectionObserver` | Browser API | Observes `#trace-analysis-container`; gates auto-refresh when off-screen |
| `navigator.clipboard` | Browser API | Copies trace / context JSON to the clipboard |

API base URL resolution: `import.meta.env.VITE_API_URL || 'http://localhost:8000'`.

## Usage Example

```tsx
import { TraceAnalysis } from '../components/features/debugging/TraceAnalysis'

// Rendered in the "traces" tab of the Debugging page
<TraceControls onConfigChange={handleTraceConfigChange} />
<TraceAnalysis
  onExport={handleTraceExport}
  refreshInterval={2000}
  initialLimit={500}
/>

// Parent-provided export handler
const handleTraceExport = (format: 'json' | 'csv') => {
  console.log(`Traces exported as ${format}`)
}
```

## State Used

| State | Type | Purpose |
|---|---|---|
| `traces` | `TraceEntry[]` | All loaded trace entries, sorted by `sequence` |
| `filters` | `TraceFilters` | Active filter criteria applied in `filteredTraces` |
| `isLoading` | `boolean` | Initial-load spinner state |
| `isRefreshing` | `boolean` | Refresh button spinner / disabled state |
| `autoRefresh` | `boolean` | Toggles the polling interval effect |
| `expandedTraces` | `Set<number>` | Sequence numbers of traces with expanded context panels |
| `stats` | `{ total, byFlow, byTag, timeRange? }` | Aggregated counts by flow and tag plus time range, computed in `calculateStats` |
| `isVisible` | `useRef<boolean>` | Updated by IntersectionObserver; gates auto-refresh fetches |

Derived: `filteredTraces` — `traces` filtered by flow name, sequence range, step search, include/exclude text (OR logic), tags (ANY-of), and time range.

## Related Components

- **Parent**: `frontend/src/pages/Debugging.tsx` — renders `<TraceAnalysis onExport={handleTraceExport} />` in the `traces` tab, alongside `TraceControls`.
- **Siblings** (same `frontend/src/components/features/debugging/` directory): `TraceControls.tsx`, `BackendTraceViewer.tsx`, `CognitiveTraceViewer.tsx`, `ErrorAnalysis.tsx`, `LogViewer.tsx`, `LiveMonitoring.tsx`, `DatabaseTools.tsx`, `DebugControls.tsx`.
- **`ErrorBoundary`**: `frontend/src/components/ErrorBoundary.tsx`.
- **`frontendLoggingService`**: `frontend/src/services/frontendLoggingService.ts`.
- **`TraceService` / `TraceTag`**: `frontend/src/services/domain/TraceService.ts` — defines the tag union and the `FlowTrace` emission this component reads back from the backend.
