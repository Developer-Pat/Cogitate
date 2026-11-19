---
title: CognitiveTraceDebugOverlay
type: atlas-component
path: frontend/src/components/features/agentInteraction/CognitiveTraceDebugOverlay.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---

# CognitiveTraceDebugOverlay

**Path**: `frontend/src/components/features/agentInteraction/CognitiveTraceDebugOverlay.tsx`
**Last Updated**: 2026-08-01

## Purpose

Development-only floating overlay that shows the raw cognitive pipeline trace events in real time while an agent message streams through the pipeline. It is a fixed-position panel (default top-left at x:16, y:60) rendered with `position: fixed` and `z-index 9999`, and is toggled with the keyboard shortcut **Ctrl+Shift+D** (with `preventDefault`). When hidden it returns `null`, so it is fully unmounted and has no runtime cost.

The overlay displays:

- **Events tab** — an ordered list of all `CognitiveEvent`s received during the current stream. Each row shows an index (`#N`), a human label (e.g. "Context Built", "Executor Started"), and — when the event data contains `duration_ms` — the formatted duration. Clicking a row expands it to show the full event `data` as pretty-printed JSON (`JSON.stringify(event.data, null, 2)`).
- **Trace tab** — a summary of the latest `CognitiveTraceCompleteEvent`: total duration, total tokens (`.toLocaleString()`), LLM calls, tool calls, cache hits, a per-component breakdown (`component:strategy` + duration + tokens), a memory-delta section (stored keys, evicted keys, compaction warning), and any pipeline error.
- **Raw State tab** — a live JSON snapshot of the entire `CognitiveState`, refreshed via `setInterval` every 500 ms while the overlay is visible.

The header shows a 🐛 Debug title, a spinner while the pipeline is active, a status pill (`executorStage` or `idle`), and a ✕ close button (tooltip "Close (Ctrl+Shift+D)"). The header is draggable: mousedown on the header starts a drag (tracked via `dragRef`), mousemove updates `position`, mouseup ends it. The footer shows "Ctrl+Shift+D to toggle" and an event-count/activity summary.

The overlay is a pure presentational consumer: it holds no pipeline logic and does not subscribe to the streaming service — it only renders the `CognitiveState` passed in via props. Note: the file header comment claims rows show "timestamps", but the rendered rows actually show index + label + duration; the `formatTimestamp()` helper exists but is currently unused (dead code) — nothing timestamp-related is rendered.

## Props Interface

```tsx
interface CognitiveTraceDebugOverlayProps {
  cognitiveState: CognitiveState
  getCognitiveState: () => CognitiveState
}
```

`CognitiveState` is defined in `frontend/src/services/domain/StreamingService.ts`:

```ts
export interface CognitiveState {
  /** Ordered list of cognitive events received during the current stream */
  events: CognitiveEvent[]
  /** Latest trace data (set when cognitive_trace_complete arrives) */
  latestTrace: CognitiveTraceCompleteEvent | null
  /** Whether the cognitive pipeline is currently active */
  isActive: boolean
  /** Current executor stage (e.g. 'streaming', 'thinking', 'idle') */
  executorStage: string
}
```

`CognitiveEvent` is a discriminated union of seven event types (`cognitive_context_built`, `cognitive_executor_started`, `cognitive_executor_progress`, `cognitive_executor_completed`, `cognitive_memory_updated`, `cognitive_response_formatted`, `cognitive_trace_complete`), each carrying its own `data` payload defined in the same service file.

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `react` — `useState`, `useEffect`, `useCallback`, `useRef` | Hooks | Visibility/position/tab/raw-state state; Ctrl+Shift+D keydown listener; 500 ms raw-state refresh interval; drag gesture handlers; overlay + drag refs |
| `CognitiveEvent`, `CognitiveState`, `CognitiveTraceCompleteEvent` from `../../../services/domain/StreamingService` | Types | Event rows, state shape, trace summary payload |

The component does **not** use any store, context, or service hook — it is a pure function of the props handed down from the AgentInteraction page.

## Usage Example

Mounted unconditionally in the AgentInteraction page (`frontend/src/pages/AgentInteraction.tsx`) after the main chat layout; it stays invisible until Ctrl+Shift+D is pressed:

```tsx
import CognitiveTraceDebugOverlay from '../components/features/agentInteraction/CognitiveTraceDebugOverlay'
// ...
<CognitiveTraceDebugOverlay
  cognitiveState={cognitiveState}
  getCognitiveState={getCognitiveState}
/>
```

## State Used

Local component state:

| State | Type | Default | Purpose |
|---|---|---|---|
| `visible` | `boolean` | `false` | Renders `null` when false; toggled by Ctrl+Shift+D and by the ✕ button |
| `position` | `{ x: number; y: number }` | `{ x: 16, y: 60 }` | Fixed-position top-left coordinates; updated while dragging the header |
| `activeTab` | `'events' \| 'trace' \| 'raw'` | `'events'` | Active content tab |
| `rawState` | `string` | `''` | JSON snapshot of `getCognitiveState()` refreshed every 500 ms while visible |
| `overlayRef` | `RefObject<HTMLDivElement \| null>` | `null` | Root overlay element; used for drag offset math via `getBoundingClientRect()` |
| `dragRef` | `RefObject<{ startX; startY; offsetX; offsetY } \| null>` | `null` | Drag start coordinates; cleared on mouseup |

Props-driven data (`cognitiveState`): `events` feeds the Events tab, `latestTrace` feeds the Trace tab, `isActive` drives the header spinner + status pill + footer, `executorStage` is shown in the status pill.

### Trace data shown

The Trace tab renders `CognitiveTraceCompleteEvent`, which carries:

- `trace`: per-phase `CognitiveComponentData` for the four pipeline phases — `context_builder`, `executor`, `memory_manager`, `response_formatter` — plus `total_duration_ms` and `total_tokens`. `CognitiveComponentData` = `{ component, strategy, duration_ms, tokens_used?, error?, metadata? }`.
- `metrics`: `total_duration_ms`, `total_tokens`, `llm_calls`, `tool_calls`, `cache_hits`.
- `memory_delta`: `{ stored_keys, evicted_keys, compaction_triggered }` or `null`.
- `error`: optional pipeline error string.

Per-component rows render as `component:strategy`, formatted duration, and `· N tok` when `tokens_used` is present. Durations are formatted by `formatTime()` (`ms` under 1 s, `s` under 60 s, `m` above).

Event payload shapes (from `StreamingService.ts`) include: `CognitiveContextBuiltEvent` (sources, tokens_used, duration_ms), `CognitiveExecutorStartedEvent` (strategy), `CognitiveExecutorProgressEvent` (token_count, tool_calls, stage), `CognitiveExecutorCompletedEvent` (duration_ms, tokens_used, error?), `CognitiveMemoryUpdatedEvent` (duration_ms, compaction_triggered, stored_keys, error?), `CognitiveResponseFormattedEvent` (duration_ms, error?).

## Related Components

- `frontend/src/pages/AgentInteraction.tsx` — the page that owns the streaming state and mounts the overlay (imports and renders `<CognitiveTraceDebugOverlay cognitiveState={...} getCognitiveState={...} />`).
- `frontend/src/services/domain/StreamingService.ts` — defines `CognitiveEvent`, `CognitiveState`, `CognitiveTraceCompleteEvent`, `CognitiveComponentData`, and emits the cognitive pipeline events the overlay displays.
- Sibling UI in the same directory: `frontend/src/components/features/agentInteraction/` (chat/message components that share the page's streaming state).
